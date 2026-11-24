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
    """The union of the unique PP boxes of the cells, or None when no box is sure."""
    used = []
    for cell in cells:
        c = letters(cell)
        if len(c) < 2:
            continue
        cands = [box for text, box in inside if c in text]
        if len(cands) == 1:
            used.append(cands[0])
    if not used or not all(overlap_vertically(a, b) for i, a in enumerate(used) for b in used[i + 1:]):
        return None
    return [min(b[0] for b in used), min(b[1] for b in used), max(b[2] for b in used), max(b[3] for b in used)]


def page_line_boxes(record_page, second_lines=None, second_size=None):
    """One {"box", "level"} for every line of plain_lines(record_page), in the same order. The page needs width and
    height and a bbox on every block."""
    size = (record_page["width"], record_page["height"])
    block_boxes = [normalize(b["bbox"], size) if b.get("bbox") else None for b in record_page["blocks"]]
    pp = []
    if second_lines and second_size:
        pp = [(letters(l["text"]), normalize(l["box"], second_size)) for l in second_lines]
    out = []
    for line, n in plain_lines(record_page):
        block = block_boxes[n]
        inside = [(t, b) for t, b in pp
                  if block[0] <= (b[0] + b[2]) / 2 <= block[2] and block[1] <= (b[1] + b[3]) / 2 <= block[3]]
        box = line_box(line.split(CELL_SEP), inside) if inside else None
        out.append({"box": box, "level": "line"} if box else {"box": block, "level": "block"})
    return out


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
