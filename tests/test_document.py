"""The text document from reader blocks. No model is loaded:
  python -m unittest discover -s tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ocr_text_basic.document import text_document
from ocr_text_basic.mask import MASK

HTML = ("<table><tr><td>구분</td><td>금액</td></tr><tr><td>수업료</td><td>300,000</td></tr>"
        "<tr><td>성명</td><td>모의새봄</td></tr><tr><td colspan=\"2\">비고</td></tr></table>")
RECORD = {"doc": "x", "pages": [
    {"page": 1, "blocks": [{"label": "header_image", "content": ""},
                           {"label": "paragraph_title", "content": "등록금 납부 확인서"},
                           {"label": "text", "content": "학기 : 2024학년도 제1학기\n연락처 010-1234-5678"},
                           {"label": "table", "content": HTML}]},
    {"page": 2, "blocks": [{"label": "text", "content": "발급일 2024.03.10"}]}]}


class TextDocumentTest(unittest.TestCase):
    def test_only_document_and_pages_with_page_and_text(self):
        doc = text_document(RECORD, {"student_name": "모의새봄"})
        self.assertEqual(set(doc), {"document", "pages"})
        self.assertEqual(doc["document"], {"doc_id": "x"})
        self.assertEqual([set(p) for p in doc["pages"]], [{"page", "text"}, {"page", "text"}])
        self.assertEqual([p["page"] for p in doc["pages"]], [1, 2])

    def test_text_blocks_are_lines_and_table_rows_are_cells_joined(self):
        text = text_document(RECORD, {"student_name": "모의새봄"})["pages"][0]["text"]
        self.assertEqual(text[0], "등록금 납부 확인서")
        self.assertEqual(text[1], "학기 : 2024학년도 제1학기")
        self.assertIn("구분 | 금액", text)
        self.assertIn("수업료 | 300,000", text)
        self.assertIn("비고", text)

    def test_identity_values_are_masked(self):
        doc = text_document(RECORD, {"student_name": "모의새봄"})
        text = doc["pages"][0]["text"]
        self.assertNotIn("모의새봄", json.dumps(doc, ensure_ascii=False))
        self.assertIn(f"성명 | {MASK}", text)
        self.assertNotIn("010-1234-5678", json.dumps(doc, ensure_ascii=False))

    def test_without_application_values_the_shapes_and_labels_still_mask(self):
        text = text_document(RECORD, None)["pages"][0]["text"]
        self.assertIn(f"성명 | {MASK}", text)
        self.assertFalse(any("010-1234-5678" in line for line in text))

    def test_the_cli_writes_the_document_from_a_stored_reader_record(self):
        with tempfile.TemporaryDirectory() as d:
            raw, out = Path(d) / "x.json", Path(d) / "out.json"
            raw.write_text(json.dumps(RECORD, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, "-m", "ocr_text_basic", "--from-raw", str(raw), "-o", str(out)], check=True)
            doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(set(doc), {"document", "pages"})
        self.assertIn("수업료 | 300,000", doc["pages"][0]["text"])


if __name__ == "__main__":
    unittest.main()
