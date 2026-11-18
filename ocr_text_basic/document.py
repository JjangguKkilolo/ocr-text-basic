"""Reader blocks to the text document {"document": {"doc_id"}, "pages": [{"page", "text"}]}. No model call.

A text block is split into lines. A table block is HTML: rows, cells, rowspan and colspan place the cells by the HTML
table rule, every row becomes one line of its cell texts joined by CELL_SEP, and no cell is judged a header. Every
line is masked (ocr_text_basic.mask); the cells of one table row are masked as one word sequence so a label in one
cell (성명) masks the value in the next cell.
"""
from html.parser import HTMLParser

from ocr_text_basic.mask import MASK, default_profile, mask_spans, mask_words

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


def masked_text(text, applicant, profile):
    words = (text or "").split()
    spans = mask_spans(words, applicant, 8)
    return " ".join(MASK if i in spans else w for i, w in enumerate(mask_words(words, applicant, profile)))


def mask_row_cells(cells, applicant, profile):
    by_row = {}
    for c in cells:
        by_row.setdefault(c["row"], []).append(c)
    for row in by_row.values():
        row.sort(key=lambda c: c["col"])
        words = [c["text"].split() for c in row]
        flat_words = [w for ws in words for w in ws]
        cell_of = [n for n, ws in enumerate(words) for _ in ws]
        spans = mask_spans(flat_words, applicant, 8)
        masked = [MASK if i in spans else w for i, w in enumerate(mask_words(flat_words, applicant, profile, cell_of))]
        at = 0
        for c, ws in zip(row, words):
            c["text"] = " ".join(masked[at:at + len(ws)])
            at += len(ws)


def row_lines(cells):
    """One line for every table row: the texts of the cells that start in the row, in column order."""
    rows = {}
    for c in sorted(cells, key=lambda c: (c["row"], c["col"])):
        if c["text"]:
            rows.setdefault(c["row"], []).append(c["text"])
    return [CELL_SEP.join(rows[r]) for r in sorted(rows)]


def page_text(blocks, applicant=None, profile=None):
    profile = profile or default_profile()
    text = []
    for block in blocks:
        if block["label"] == "table":
            cells = html_cells(block["content"])
            mask_row_cells(cells, applicant, profile)
            text += row_lines(cells)
        elif block["content"]:
            text += [masked_text(line, applicant, profile) for line in block["content"].split("\n") if line.strip()]
    return text


def text_document(record, applicant=None, profile=None):
    """record: {"doc", "pages": [{"page", "blocks": [{"label", "content"}]}]} as ocr_text_basic.read writes it.
    applicant: the application values to mask ({"student_name": ..., "student_id": ..., "birth_date": ...}) or None."""
    return {"document": {"doc_id": record["doc"]},
            "pages": [{"page": p["page"], "text": page_text(p["blocks"], applicant, profile)} for p in record["pages"]]}
