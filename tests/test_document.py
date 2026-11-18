"""The text document and the masked values from reader blocks. No model is loaded:
  python -m unittest discover -s tests
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ocr_text_basic.document import build, text_document

HTML = ("<table><tr><td>구분</td><td>금액</td></tr><tr><td>수업료</td><td>300,000</td></tr>"
        "<tr><td>성명</td><td>모의새봄</td></tr><tr><td colspan=\"2\">비고</td></tr></table>")
RECORD = {"doc": "x", "pages": [
    {"page": 1, "blocks": [{"label": "header_image", "content": ""},
                           {"label": "paragraph_title", "content": "등록금 납부 확인서"},
                           {"label": "text", "content": "학기 : 2024학년도 제1학기\n연락처 010-1234-5678"},
                           {"label": "table", "content": HTML}]},
    {"page": 2, "blocks": [{"label": "text", "content": "발급일 2024.03.10\n학번 : 202435982\n담당 : 모의하늘"}]}]}
APPLICANT = {"student_name": "모의새봄"}
TOKEN = re.compile(r"\[가림#(\d+)\]")


def entry(masked, line):
    return next(m for m in masked if m["id"] == int(TOKEN.search(line).group(1)))


class TextDocumentTest(unittest.TestCase):
    def test_only_document_and_pages_with_page_and_text(self):
        doc = text_document(RECORD, APPLICANT)
        self.assertEqual(set(doc), {"document", "pages"})
        self.assertEqual(doc["document"], {"doc_id": "x"})
        self.assertEqual([set(p) for p in doc["pages"]], [{"page", "text"}, {"page", "text"}])
        self.assertEqual([p["page"] for p in doc["pages"]], [1, 2])

    def test_text_blocks_are_lines_and_table_rows_are_cells_joined(self):
        text = text_document(RECORD, APPLICANT)["pages"][0]["text"]
        self.assertEqual(text[0], "등록금 납부 확인서")
        self.assertEqual(text[1], "학기 : 2024학년도 제1학기")
        self.assertIn("구분 | 금액", text)
        self.assertIn("수업료 | 300,000", text)
        self.assertIn("비고", text)

    def test_identity_values_are_masked_with_a_numbered_token(self):
        doc = text_document(RECORD, APPLICANT)
        dumped = json.dumps(doc, ensure_ascii=False)
        self.assertNotIn("모의새봄", dumped)
        self.assertNotIn("010-1234-5678", dumped)
        self.assertNotIn("202435982", dumped)
        self.assertRegex(doc["pages"][0]["text"][5], r"^성명 \| \[가림#\d+\]$")

    def test_without_application_values_the_shapes_and_labels_still_mask(self):
        text = text_document(RECORD, None)["pages"][0]["text"]
        self.assertRegex(text[-2], r"^성명 \| \[가림#\d+\]$")
        self.assertFalse(any("010-1234-5678" in line for line in text))


class MaskedValuesTest(unittest.TestCase):
    def test_every_token_has_its_value_and_reason(self):
        doc, side = build(RECORD, APPLICANT)
        masked = side["masked"]
        page1, page2 = doc["pages"][0]["text"], doc["pages"][1]["text"]
        self.assertEqual(entry(masked, page1[5]),
                         {"id": entry(masked, page1[5])["id"], "page": 1, "value": "모의새봄", "reason": "application",
                          "field": "student_name"})
        phone = entry(masked, page1[2])
        self.assertEqual((phone["value"], phone["reason"], phone["shape"]), ("010-1234-5678", "shape", "phone"))
        number = entry(masked, page2[1])
        self.assertEqual((number["page"], number["value"], number["reason"], number["shape"]),
                         (2, ": 202435982", "shape", "digits"))
        serial = entry(masked, page2[2])
        self.assertEqual((serial["value"], serial["reason"], serial["label"]), (": 모의하늘", "label", "담당"))

    def test_masked_words_next_to_each_other_are_one_token_and_ids_count_up(self):
        doc, side = build(RECORD, APPLICANT)
        masked = side["masked"]
        self.assertEqual(doc["pages"][1]["text"][1:], [f"학번 [가림#{len(masked) - 1}]", f"담당 [가림#{len(masked)}]"])
        tokens = [int(n) for p in doc["pages"] for line in p["text"] for n in TOKEN.findall(line)]
        self.assertEqual(tokens, list(range(1, len(masked) + 1)))
        self.assertEqual([m["id"] for m in masked], tokens)

    def test_putting_the_values_back_gives_the_read_text(self):
        doc, side = build(RECORD, APPLICANT)
        masked = side["masked"]
        values = {m["id"]: m["value"] for m in masked}
        back = [TOKEN.sub(lambda t: values[int(t.group(1))], line) for p in doc["pages"] for line in p["text"]]
        self.assertIn("연락처 010-1234-5678", back)
        self.assertIn("성명 | 모의새봄", back)
        self.assertIn("학번 : 202435982", back)
        self.assertIn("담당 : 모의하늘", back)


class CommandLineTest(unittest.TestCase):
    def test_the_cli_writes_the_document_and_the_masked_values_to_separate_files(self):
        with tempfile.TemporaryDirectory() as d:
            raw, out, hidden, app = (Path(d) / n for n in ("x.json", "out.json", "masked.json", "app.json"))
            raw.write_text(json.dumps(RECORD, ensure_ascii=False), encoding="utf-8")
            app.write_text(json.dumps(APPLICANT, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, "-m", "ocr_text_basic", "--from-raw", str(raw), "-o", str(out),
                            "--masked-out", str(hidden), "--applicant", str(app)], check=True)
            doc = json.loads(out.read_text(encoding="utf-8"))
            side = json.loads(hidden.read_text(encoding="utf-8"))
        self.assertEqual(set(doc), {"document", "pages"})
        self.assertIn("수업료 | 300,000", doc["pages"][0]["text"])
        self.assertNotIn("모의새봄", json.dumps(doc, ensure_ascii=False))
        self.assertEqual(side["document"], {"doc_id": "x"})
        self.assertIn("모의새봄", [m["value"] for m in side["masked"]])


if __name__ == "__main__":
    unittest.main()
