"""Reader blocks to the text document {"document": {"doc_id"}, "pages": [{"page", "text"}]} and the masked values
{"document": {"doc_id"}, "masked": [{"id", "page", "value", "reason", ...}]}. No model call.

A text block is split into lines. A table block is HTML: rows, cells, rowspan and colspan place the cells by the HTML
table rule, every row becomes one line of its cell texts joined by CELL_SEP, and no cell is judged a header. Every
line is masked (ocr_text_basic.mask); the cells of one table row are masked as one word sequence so a label in one
cell (성명) masks the value in the next cell. Masked words next to each other in one line or one table cell become
one token [가림#id]; ids count from 1 in reading order over the whole document, and the masked values give every id
its original words and why they were masked (application with its field, shape with its shape, label with its label
word, or institution).
"""
from html.parser import HTMLParser

from ocr_text_basic.mask import default_profile, mask_reasons, span_fields

CELL_SEP = " | "


class TableHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells, self.taken, self.row, self.open = [], set(), -1, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row += 1
        elif tag in ("td", "th"):
            a = dict(attrs)

            def span(k):
                v = str(a.get(k) or "1")
                return max(1, int(v)) if v.isdigit() else 1
            col = 0
            while (self.row, col) in self.taken:
                col += 1
            cell = {"row": self.row, "col": col, "row_span": span("rowspan"), "col_span": span("colspan"), "text": ""}
            self.taken |= {(r, c) for r in range(cell["row"], cell["row"] + cell["row_span"])
                           for c in range(col, col + cell["col_span"])}
            self.cells.append(cell)
            self.open = cell

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.open = None

    def handle_data(self, data):
        if self.open is not None:
            self.open["text"] += data


def html_cells(html):
    parser = TableHTML()
    parser.feed(html or "")
    for cell in parser.cells:
        # the reader writes a line break inside a cell as the two characters backslash and n
        cell["text"] = cell["text"].replace("\\n", " ").strip()
    return parser.cells


# the reason that names a run of masked words: a value of the application first, then a shape, then a label
PRIORITY = ("application", "shape", "label", "institution")


def reasons_of(words, applicant, profile, cells=None):
    reasons = mask_reasons(words, applicant, profile, cells)
    for i, key in span_fields(words, applicant, 8).items():
        if not reasons[i] or reasons[i]["reason"] != "application":
            reasons[i] = {"reason": "application", "field": key}
    return reasons


class Masked:
    """The masked values of one document and the numbered tokens that replace them."""
    def __init__(self):
        self.values = []

    def render(self, page, words, reasons):
        out, i = [], 0
        while i < len(words):
            if not reasons[i]:
                out.append(words[i])
                i += 1
                continue
            j = i
            while j < len(words) and reasons[j]:
                j += 1
            reason = min(reasons[i:j], key=lambda r: PRIORITY.index(r["reason"]))
            self.values.append({"id": len(self.values) + 1, "page": page, "value": " ".join(words[i:j]), **reason})
            out.append(f"[가림#{len(self.values)}]")
            i = j
        return " ".join(out)


def mask_row_cells(cells, applicant, profile, page, masked):
    by_row = {}
    for c in cells:
        by_row.setdefault(c["row"], []).append(c)
    for row in sorted(by_row.values(), key=lambda r: r[0]["row"]):
        row.sort(key=lambda c: c["col"])
        words = [c["text"].split() for c in row]
        flat_words = [w for ws in words for w in ws]
        cell_of = [n for n, ws in enumerate(words) for _ in ws]
        reasons = reasons_of(flat_words, applicant, profile, cell_of)
        at = 0
        for c, ws in zip(row, words):
            c["text"] = masked.render(page, ws, reasons[at:at + len(ws)])
            at += len(ws)


def row_lines(cells):
    """One line for every table row: the texts of the cells that start in the row, in column order."""
    rows = {}
    for c in sorted(cells, key=lambda c: (c["row"], c["col"])):
        if c["text"]:
            rows.setdefault(c["row"], []).append(c["text"])
    return [CELL_SEP.join(rows[r]) for r in sorted(rows)]


def page_text(page, blocks, applicant, profile, masked):
    text = []
    for block in blocks:
        if block["label"] == "table":
            cells = html_cells(block["content"])
            mask_row_cells(cells, applicant, profile, page, masked)
            text += row_lines(cells)
        elif block["content"]:
            for line in block["content"].split("\n"):
                if line.strip():
                    words = line.split()
                    text.append(masked.render(page, words, reasons_of(words, applicant, profile)))
    return text


def plain_pages(record):
    """The lines of every page as build writes them, unmasked: same order, same lines, same cells per line. For
    comparing with a second reader inside the code only; never write these to an output."""
    pages = []
    for page in record["pages"]:
        text = []
        for block in page["blocks"]:
            if block["label"] == "table":
                cells = html_cells(block["content"])
                for c in cells:
                    c["text"] = " ".join(c["text"].split())
                text += row_lines(cells)
            elif block["content"]:
                text += [" ".join(line.split()) for line in block["content"].split("\n") if line.strip()]
        pages.append(text)
    return pages


def build(record, applicant=None, profile=None):
    """(text document, masked values) of one reader record. record: {"doc", "pages": [{"page", "blocks": [{"label",
    "content"}]}]} as ocr_text_basic.read writes it. applicant: the application values to mask ({"student_name": ...,
    "student_id": ..., "birth_date": ...}) or None."""
    profile = profile or default_profile()
    masked = Masked()
    pages = [{"page": p["page"], "text": page_text(p["page"], p["blocks"], applicant, profile, masked)}
             for p in record["pages"]]
    doc_id = {"doc_id": record["doc"]}
    return {"document": doc_id, "pages": pages}, {"document": doc_id, "masked": masked.values}


def text_document(record, applicant=None, profile=None):
    return build(record, applicant, profile)[0]
