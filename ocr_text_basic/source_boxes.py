"""Where each output line came from: a box on the page image for every text line, from the block boxes of the reader
(VL) and the unique matches of second reader (PP) lines. A line box needs a PP line inside the block that holds the
line's cell text and no other PP line inside the block that does. When in doubt the line gets its block box. The
comparison uses the unmasked letters inside the code only; no letters are written to the output."""
import unicodedata

from ocr_text_basic.document import CELL_SEP, plain_lines


def letters(s):
    return "".join(ch for ch in unicodedata.normalize("NFC", s or "")
                   if unicodedata.category(ch).startswith("L") or unicodedata.category(ch) == "Nd")


def has_boxes(record):
    pages = record.get("pages") or []
    if not pages:
        return False
    return all(p.get("width") and p.get("height") and all(b.get("bbox") for b in p["blocks"]) for p in pages)


def normalize(box, size):
    w, h = size
    x0, y0, x1, y1 = box
    return [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]


def overlap_vertically(a, b):
    return a[1] < b[3] and b[1] < a[3]


def line_box(cells, inside):
    """(union of the unique PP boxes of the cells, the indexes of the PP lines used), or (None, set()) when no box is
    sure. A PP line is a candidate only when its letters are part of the letters of the whole line."""
    own = letters("".join(cells))
    used = []
    for cell in cells:
        c = letters(cell)
        if len(c) < 2:
            continue
        cands = [(i, box) for i, text, box in inside if c in text and text in own]
        if len(cands) == 1:
            used.append(cands[0])
    boxes = [b for _, b in used]
    if not boxes or not all(overlap_vertically(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:]):
        return None, set()
    union = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    return union, {i for i, _ in used}


def page_line_boxes(record_page, second_lines=None, second_size=None):
    """One {"box", "level"} for every line of plain_lines(record_page), in the same order. The page needs width and
    height and a bbox on every block. A PP line used by two lines of the page is used by none."""
    size = (record_page["width"], record_page["height"])
    block_boxes = [normalize(b["bbox"], size) if b.get("bbox") else None for b in record_page["blocks"]]
    pp = []
    if second_lines and second_size:
        pp = [(i, letters(l["text"]), normalize(l["box"], second_size)) for i, l in enumerate(second_lines)]
    found, used_by = [], {}
    for k, (line, n) in enumerate(plain_lines(record_page)):
        block = block_boxes[n]
        inside = [(i, t, b) for i, t, b in pp
                  if block[0] <= (b[0] + b[2]) / 2 <= block[2] and block[1] <= (b[1] + b[3]) / 2 <= block[3]]
        cells = line.split(CELL_SEP) if record_page["blocks"][n]["label"] == "table" else [line]
        box, used = line_box(cells, inside) if inside else (None, set())
        found.append((box, block))
        for i in used:
            used_by.setdefault(i, []).append(k)
    shared = {k for ks in used_by.values() if len(ks) > 1 for k in ks}
    return [{"box": box, "level": "line"} if box and k not in shared else {"box": block, "level": "block"}
            for k, (box, block) in enumerate(found)]


def add_boxes(text_doc, record, second_pages=None, second_sizes=None):
    """A new text document where every page also holds source {"file", "file_page"} and line_boxes. A record without
    the sizes and boxes (an old record) gives text_doc unchanged."""
    if not has_boxes(record):
        return text_doc
    pages = []
    for k, (page, rec) in enumerate(zip(text_doc["pages"], record["pages"])):
        lines = second_pages[k] if second_pages is not None and k < len(second_pages) else None
        size = second_sizes[k] if second_sizes is not None and k < len(second_sizes) else None
        pages.append(dict(page, source={"file": rec.get("file"), "file_page": rec.get("file_page")},
                          line_boxes=page_line_boxes(rec, lines, size)))
    return dict(text_doc, pages=pages)
