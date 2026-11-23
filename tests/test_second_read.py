"""Second PaddleOCR-VL read on enlarged pages (two-tier flags design 2026-11-23). No model is loaded."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ocr_text_basic.second_read import enlarged_pages, second_read_pages


class FakeResult:
    def __init__(self, res):
        self.json = {"res": res}


class FakeVL:
    def __init__(self):
        self.seen = []

    def predict(self, path):
        self.seen.append(str(path))
        return [FakeResult({"parsing_res_list": [{"block_label": "text", "block_content": "등록금 납부 확인서", "block_order": 1}]})]


class SecondReadTest(unittest.TestCase):
    def test_enlarged_pages_sizes_and_order(self):
        import pypdfium2
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf = pypdfium2.PdfDocument.new()
            pdf.new_page(72, 144)
            pdf.new_page(72, 144)
            pdf.save(str(tmp / "a.pdf"))
            Image.new("RGB", (100, 200), "white").save(tmp / "b.png")
            out = enlarged_pages([str(tmp / "a.pdf"), str(tmp / "b.png")], tmp / "w")
            self.assertEqual(len(out), 3)
            sizes = [Image.open(p).size for p in out]
            self.assertEqual(sizes[0], (180, 360))
            self.assertEqual(sizes[1], (180, 360))
            self.assertEqual(sizes[2], (125, 250))

    def test_odd_sizes_match_the_calibration_resize(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            noise = np.random.default_rng(1).integers(0, 255, (777, 1003, 3), dtype=np.uint8)
            cv2.imwrite(str(tmp / "n.png"), noise)
            out = cv2.imread(str(enlarged_pages([str(tmp / "n.png")], tmp / "w")[0]))
            expected = cv2.resize(noise, (round(1003 * 1.25), round(777 * 1.25)), interpolation=cv2.INTER_CUBIC)
            self.assertTrue(np.array_equal(out, expected))

    def test_same_stems_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a").mkdir()
            (tmp / "b").mkdir()
            Image.new("RGB", (100, 200), "white").save(tmp / "a" / "1.png")
            Image.new("RGB", (300, 300), "white").save(tmp / "b" / "1.jpg")
            out = enlarged_pages([str(tmp / "a" / "1.png"), str(tmp / "b" / "1.jpg")], tmp / "w")
            self.assertEqual(len(set(out)), 2)
            self.assertEqual([Image.open(p).size for p in out], [(125, 250), (375, 375)])

    def test_second_read_pages_uses_enlarged_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            png = tmp / "b.png"
            Image.new("RGB", (100, 200), "white").save(png)
            fake = FakeVL()
            pages = second_read_pages([str(png)], fake, tmp / "w")
            self.assertEqual(pages, [["등록금 납부 확인서"]])
            self.assertTrue(fake.seen[0].endswith(".png"))
            self.assertNotEqual(fake.seen[0], str(png))


if __name__ == "__main__":
    unittest.main()
