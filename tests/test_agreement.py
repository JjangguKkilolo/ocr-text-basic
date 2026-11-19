"""Cell agreement with a second reader's page text. No model is loaded:
  python -m unittest discover -s tests
"""
import unittest

from ocr_text_basic.agreement import cell_status, core, line_cells, line_check
from ocr_text_basic.document import build, plain_pages

HTML = ("<table><tr><td>구분</td><td>금액</td></tr><tr><td>수업료</td><td>300,000</td></tr>"
        "<tr><td>성명</td><td>모의새봄</td></tr></table>")
RECORD = {"doc": "x", "pages": [{"page": 1, "blocks": [{"label": "text", "content": "등록금 납부 확인서\n학기 : 2024학년도"},
                                                        {"label": "table", "content": HTML}]}]}


class AgreementTest(unittest.TestCase):
    def test_core_keeps_letters_digits_and_separators_between_digits(self):
        self.assertEqual(core("수 업 료 | 3,352,000원"), "수업료3,352,000원")
        self.assertEqual(core("(㉮-㉯)"), "")
        self.assertEqual(core("2026.08.11"), "2026.08.11")

    def test_line_cells(self):
        self.assertEqual(line_cells("수 업 료 | 3,352,000"), ["수 업 료", "3,352,000"])

    def test_cell_status(self):
        other = core("수업료 3,352,000")
        self.assertEqual(cell_status("3,352,000", other), "same")
        self.assertEqual(cell_status("3,362,000", other), "differs")
        self.assertEqual(cell_status("계", other), "short")

    def test_line_check(self):
        other = core("수업료 3,352,000")
        self.assertEqual(line_check("수 업 료 | 3,362,000", other), {"agree": False, "cells": [1]})
        self.assertEqual(line_check("수 업 료 | 3,352,000", other), {"agree": True, "cells": []})
        self.assertEqual(line_check("계 | 0", other), {"agree": None, "cells": []})

    def test_plain_pages_match_build_line_count(self):
        plain = plain_pages(RECORD)
        masked = build(RECORD, {"student_name": "모의새봄"})[0]["pages"][0]["text"]
        self.assertEqual(len(plain[0]), len(masked))
        self.assertEqual([len(line_cells(a)) for a in plain[0]], [len(line_cells(b)) for b in masked])
        self.assertIn("성명 | 모의새봄", plain[0])
        self.assertFalse(any("모의새봄" in l for l in masked))


if __name__ == "__main__":
    unittest.main()
