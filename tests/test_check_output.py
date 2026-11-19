"""--check output: page quality and line agreement with measured error rates. No model is loaded."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ocr_text_basic.document import build, checked
from ocr_text_basic.trust_table import band_key, lookup

HTML = ("<table><tr><td>구분</td><td>금액</td></tr><tr><td>수업료</td><td>300,000</td></tr>"
        "<tr><td>성명</td><td>모의새봄</td></tr></table>")
RECORD = {"doc": "x", "pages": [{"page": 1, "blocks": [{"label": "text", "content": "등록금 납부 확인서"},
                                                        {"label": "table", "content": HTML}]},
                                 {"page": 2, "blocks": []}]}
APPLICANT = {"student_name": "모의새봄"}
TABLE = {"version": "t1", "bands": {"image|0.05-0.15": {"cells": 900, "lines": 300, "expected_cer": 0.02,
                                                    "line_error": {"true": 0.002, "false": 0.6}}}}
SECOND = [[{"text": "등록금 납부 확인서"}, {"text": "구분"}, {"text": "금액"}, {"text": "수업료"}, {"text": "800,000"},
           {"text": "성명"}, {"text": "모의새봄"}], []]
SIGNALS = [{"short_side_px": 1654, "dpi": 200.0, "sharpness": 900.0, "contrast": 200.0, "clipped_share": 0.8}] * 2


class CheckOutputTest(unittest.TestCase):
    def doc(self, sources=("image", "image")):
        return checked(build(RECORD, APPLICANT)[0], RECORD, SECOND, SIGNALS, TABLE, list(sources))

    def test_band_key(self):
        self.assertEqual(band_key("image", 0.0), "image|<0.05")
        self.assertEqual(band_key("pdf", 0.05), "pdf|0.05-0.15")
        self.assertEqual(band_key("image", 0.4), "image|>=0.15")

    def test_check_adds_aligned_line_checks(self):
        page = self.doc()["pages"][0]
        self.assertEqual(len(page["line_checks"]), len(page["text"]))
        money = page["text"].index("수업료 | 300,000")
        self.assertEqual(page["line_checks"][money], {"agree": False, "cells": [1], "error_rate": 0.6})
        self.assertEqual(page["line_checks"][0], {"agree": True, "cells": [], "error_rate": 0.002})
        self.assertEqual(page["page_quality"]["band"], "image|0.05-0.15")  # one of seven second reader lines (800,000) is not in the VL text
        self.assertEqual(page["page_quality"]["expected_cer"], 0.02)
        self.assertEqual(self.doc()["checks"], {"second_reader": "PP-OCRv5_mobile", "table_version": "t1"})

    def test_text_is_unchanged(self):
        self.assertEqual([p["text"] for p in self.doc()["pages"]], [p["text"] for p in build(RECORD, APPLICANT)[0]["pages"]])

    def test_check_fields_hold_no_text(self):
        doc = self.doc()
        dumped = json.dumps([[p["line_checks"], p["page_quality"]] for p in doc["pages"]], ensure_ascii=False)
        self.assertNotIn("모의새봄", dumped)
        self.assertNotIn("[가림", dumped)
        self.assertNotIn("수업료", dumped)

    def test_unknown_band_gives_nulls_and_empty_page(self):
        doc = self.doc(("pdf", "pdf"))
        self.assertIsNone(doc["pages"][0]["page_quality"]["expected_cer"])
        self.assertTrue(all(c["error_rate"] is None for c in doc["pages"][0]["line_checks"]))
        empty = doc["pages"][1]
        self.assertEqual(empty["line_checks"], [])
        self.assertEqual(empty["page_quality"]["signals"]["missed_share"], 0.0)
        self.assertEqual(lookup(TABLE, "image|0.05-0.15", None), None)

    def test_without_check_output_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, out, app = Path(tmp) / "raw.json", Path(tmp) / "out.json", Path(tmp) / "app.json"
            raw.write_text(json.dumps(RECORD, ensure_ascii=False), encoding="utf-8")
            app.write_text(json.dumps(APPLICANT, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, "-m", "ocr_text_basic", "--from-raw", str(raw), "--applicant", str(app), "-o", str(out)],
                           check=True, cwd=Path(__file__).resolve().parent.parent)
            expected = json.dumps(build(RECORD, APPLICANT)[0], ensure_ascii=False, indent=1) + "\n"
            self.assertEqual(out.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
