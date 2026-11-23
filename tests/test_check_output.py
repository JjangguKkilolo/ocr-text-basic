"""--check output: page quality and line agreement with measured error rates. No model is loaded."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from ocr_text_basic.__main__ import check_document
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
TABLE2 = {"version": "t2", "strong": {"lines": 120, "line_error": 0.9},
          "bands": {"image|0.05-0.15": {"cells": 900, "lines": 300, "expected_cer": 0.02,
                                        "line_error": {"true": 0.002, "false": 0.6, "weak": 0.3}}}}
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

    def doc2(self, second_vl):
        return checked(build(RECORD, APPLICANT)[0], RECORD, SECOND, SIGNALS, TABLE2, ["image", "image"], second_vl)

    def test_strong_and_weak_with_rates(self):
        page = self.doc2([["등록금 납부 확인서", "구분 | 금액", "수업료 | 360,000", "성명 | 모의새봄"], []])["pages"][0]
        money = page["text"].index("수업료 | 300,000")
        self.assertEqual(page["line_checks"][money],
                         {"agree": False, "cells": [1], "strong_cells": [1], "level": "strong", "error_rate": 0.9})
        weak = self.doc2([["등록금 납부 확인서", "구분 | 금액", "수업료 | 300,000", "성명 | 모의새봄"], []])["pages"][0]
        self.assertEqual(weak["line_checks"][money]["level"], "weak")
        self.assertEqual(weak["line_checks"][money]["error_rate"], 0.3)
        self.assertEqual(weak["line_checks"][0], {"agree": True, "cells": [], "error_rate": 0.002})
        self.assertEqual(self.doc2([[], []])["checks"]["second_read"], "PaddleOCR-VL x1.25")

    def test_missing_second_read_page_falls_back(self):
        page = self.doc2([])["pages"][0]
        money = page["text"].index("수업료 | 300,000")
        self.assertEqual(page["line_checks"][money], {"agree": False, "cells": [1], "error_rate": 0.6})

    def test_old_table_gives_null_rates_for_levels(self):
        doc = checked(build(RECORD, APPLICANT)[0], RECORD, SECOND, SIGNALS, TABLE, ["image", "image"],
                      [["수업료 | 360,000"], []])
        money = doc["pages"][0]["text"].index("수업료 | 300,000")
        self.assertIsNone(doc["pages"][0]["line_checks"][money]["error_rate"])

    def test_level_fields_hold_no_text(self):
        doc = self.doc2([["수업료 | 360,000 모의새봄"], []])
        dumped = json.dumps([[p["line_checks"], p["page_quality"]] for p in doc["pages"]] + [doc["checks"]], ensure_ascii=False)
        for word in ("모의새봄", "[가림", "수업료", "360,000"):
            self.assertNotIn(word, dumped)

    def test_check_document_passes_second_read(self):
        record1 = dict(RECORD, pages=RECORD["pages"][:1])
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "a.png"
            Image.new("RGB", (100, 200), "white").save(png)
            with mock.patch("ocr_text_basic.second_reader.second_pipeline", return_value=object()), \
                 mock.patch("ocr_text_basic.second_reader.second_lines", return_value=SECOND[0]), \
                 mock.patch("ocr_text_basic.second_read.second_read_pages", return_value=[["수업료 | 360,000"]]) as vl2:
                doc = check_document(build(record1, APPLICANT)[0], record1, [str(png)], vl_reader="vl")
        self.assertEqual(vl2.call_args.args[:2], ([str(png)], "vl"))
        self.assertEqual(doc["checks"]["second_read"], "PaddleOCR-VL x1.25")
        flagged = [c for c in doc["pages"][0]["line_checks"] if c["agree"] is False]
        self.assertEqual(flagged[0]["level"], "strong")

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
