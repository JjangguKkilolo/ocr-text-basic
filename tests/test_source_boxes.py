"""Per-line source boxes from block boxes and unique second reader matches. No model is loaded."""
import unittest

from ocr_text_basic.document import plain_lines, plain_pages
from ocr_text_basic.source_boxes import add_boxes, has_boxes, page_line_boxes
from tests import test_document

EXPECTED_PLAIN = [['등록금 납부 확인서', '학기 : 2024학년도 제1학기', '연락처 010-1234-5678', '구분 | 금액', '수업료 | 300,000',
                   '성명 | 모의새봄', '비고'], ['발급일 2024.03.10', '학번 : 202435982', '담당 : 모의하늘']]


def table(*rows):
    return "<table>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"


def page(table_rows):
    return {"page": 1, "file": 1, "file_page": 1, "width": 1000, "height": 1000, "blocks": [
        {"label": "text", "content": "등록금 납부 확인서", "order": 1, "bbox": [100, 50, 900, 100]},
        {"label": "table", "content": table(*table_rows), "order": 2, "bbox": [100, 200, 900, 500]}]}


PAGE = page([("수업료", "300,000"), ("교육비", "300,000"), ("합계", "600,000")])
PAGE_ROW_600 = page([("수업료", "600,000")])


def pp(text, x0, y0, x1, y1):
    return {"text": text, "score": 0.99, "box": [x0, y0, x1, y1]}


class LineBoxTest(unittest.TestCase):
    def test_text_line_gets_its_pp_box(self):
        boxes = page_line_boxes(PAGE, [pp("등록금 납부 확인서", 220, 110, 1780, 190)], (2000, 2000))
        self.assertEqual(boxes[0], {"box": [0.11, 0.055, 0.89, 0.095], "level": "line"})

    def test_table_row_unions_its_unique_cells(self):
        lines = [pp("수업료", 220, 420, 500, 460), pp("300,000", 1200, 420, 1700, 460),
                 pp("교육비", 220, 520, 500, 560), pp("300,000", 1200, 520, 1700, 560)]
        boxes = page_line_boxes(PAGE, lines, (2000, 2000))
        self.assertEqual(boxes[1], {"box": [0.11, 0.21, 0.25, 0.23], "level": "line"})  # 300,000 matches two lines: dropped

    def test_cells_matching_different_rows_fall_back_to_the_block(self):
        lines = [pp("수업료", 220, 420, 500, 460), pp("600,000", 1200, 620, 1700, 660)]
        boxes = page_line_boxes(PAGE_ROW_600, lines, (2000, 2000))
        self.assertEqual(boxes[1], {"box": [0.1, 0.2, 0.9, 0.5], "level": "block"})

    def test_no_pp_lines_gives_block_boxes_for_every_line(self):
        boxes = page_line_boxes(PAGE)
        self.assertEqual([b["level"] for b in boxes], ["block"] * 4)
        self.assertEqual(len(boxes), len(plain_lines(PAGE)))

    def test_pp_line_outside_the_block_is_not_used(self):
        boxes = page_line_boxes(PAGE, [pp("등록금 납부 확인서", 220, 1800, 1780, 1900)], (2000, 2000))
        self.assertEqual(boxes[0]["level"], "block")

    def test_plain_pages_unchanged(self):
        self.assertEqual(plain_pages(test_document.RECORD), EXPECTED_PLAIN)

    def test_plain_lines_gives_the_block_index_counting_empty_blocks(self):
        rec = {"blocks": [{"label": "header_image", "content": ""}, {"label": "text", "content": "가나\n\n다라"},
                          {"label": "table", "content": table(("마", "바"))}]}
        self.assertEqual(plain_lines(rec), [("가나", 1), ("다라", 1), ("마 | 바", 2)])


class GuardTest(unittest.TestCase):
    def test_text_line_with_separator_is_one_cell(self):
        rec = {"width": 1000, "height": 1000, "blocks": [
            {"label": "text", "content": "가나다 | 라마바", "order": 1, "bbox": [100, 100, 900, 200]}]}
        whole = page_line_boxes(rec, [pp("가나다 | 라마바", 200, 220, 1700, 380)], (2000, 2000))
        self.assertEqual(whole[0]["level"], "line")
        half = page_line_boxes(rec, [pp("가나다", 200, 220, 700, 380)], (2000, 2000))
        self.assertEqual(half[0]["level"], "block")

    def test_pp_line_with_text_of_another_line_is_not_used(self):
        pg = page([("합계", "10"), ("발급일", "2024.03.10")])
        lines = [pp("발급일", 220, 420, 500, 460), pp("2024.03.10", 1200, 420, 1700, 460)]
        boxes = page_line_boxes(pg, lines, (2000, 2000))
        self.assertEqual(boxes[1]["level"], "block")
        self.assertEqual(boxes[2]["level"], "line")

    def test_pp_line_used_by_two_lines_drops_both(self):
        pg = page([("소계", "100원"), ("소계", "200원")])
        boxes = page_line_boxes(pg, [pp("소계", 220, 420, 500, 460)], (2000, 2000))
        self.assertEqual([b["level"] for b in boxes[1:]], ["block", "block"])

    def test_pp_lines_claimed_by_a_line_that_fell_back_still_count_as_used(self):
        # Codex review 2026-11-24: the first row falls back (its two PP lines do not overlap vertically) but its
        # unique PP lines still count, so the rows sharing them fall back too
        pg = page([("소계", "100원"), ("소계", "200원"), ("기타", "100원")])
        lines = [pp("소계", 120, 220, 250, 240), pp("기타", 120, 400, 250, 430), pp("100원", 600, 400, 850, 430)]
        boxes = page_line_boxes(pg, lines, (1000, 1000))
        self.assertEqual([b["level"] for b in boxes[1:]], ["block", "block", "block"])


class AddBoxesTest(unittest.TestCase):
    RECORD = {"doc": "x", "pages": [PAGE]}
    DOC = {"document": {"doc_id": "x"}, "pages": [{"page": 1, "text": ["a", "b", "c", "d"]}]}

    def test_has_boxes(self):
        self.assertTrue(has_boxes(self.RECORD))
        self.assertFalse(has_boxes({"doc": "x", "pages": []}))
        self.assertFalse(has_boxes({"doc": "x", "pages": [dict(PAGE, width=None)]}))
        blocks = [dict(PAGE["blocks"][0], bbox=None), PAGE["blocks"][1]]
        self.assertFalse(has_boxes({"doc": "x", "pages": [dict(PAGE, blocks=blocks)]}))

    def test_old_record_gives_the_document_unchanged(self):
        old = {"doc": "x", "pages": [dict(PAGE, width=None)]}
        self.assertEqual(add_boxes(self.DOC, old), self.DOC)

    def test_file_name_instead_of_number_gives_the_document_unchanged(self):
        rec = {"doc": "x", "pages": [dict(PAGE, file="a.pdf")]}
        self.assertEqual(add_boxes(self.DOC, rec), self.DOC)

    def test_adds_source_and_line_boxes_without_changing_the_input(self):
        out = add_boxes(self.DOC, self.RECORD, [[pp("등록금 납부 확인서", 220, 110, 1780, 190)]], [(2000, 2000)])
        p = out["pages"][0]
        self.assertEqual(p["source"], {"file": 1, "file_page": 1})
        self.assertEqual(len(p["line_boxes"]), len(p["text"]))
        self.assertEqual(p["line_boxes"][0]["level"], "line")
        self.assertEqual(p["text"], self.DOC["pages"][0]["text"])
        self.assertNotIn("line_boxes", self.DOC["pages"][0])

    def test_without_second_pages_every_box_is_a_block(self):
        out = add_boxes(self.DOC, self.RECORD)
        self.assertEqual({b["level"] for b in out["pages"][0]["line_boxes"]}, {"block"})


if __name__ == "__main__":
    unittest.main()
