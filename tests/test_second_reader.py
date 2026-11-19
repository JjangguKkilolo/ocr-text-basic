"""Second reader inputs and line filtering, and page image signals. No model is loaded."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ocr_text_basic.page_signals import image_signals, missed_share
from ocr_text_basic.second_reader import page_images, second_lines


class FakeResult:
    def __init__(self, res):
        self.json = {"res": res}


class FakeReader:
    def predict(self, path):
        return [FakeResult({"rec_texts": ["수업료", "흐림"], "rec_scores": [0.98, 0.4], "rec_boxes": [[1, 2, 3, 4], [5, 6, 7, 8]]})]


def text_image():
    image = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(image)
    for k in range(8):
        draw.rectangle((40 + 90 * k, 150, 80 + 90 * k, 250), fill="black")
    return image


class SecondReaderTest(unittest.TestCase):
    def test_page_images_renders_each_pdf_page_and_keeps_images(self):
        import pypdfium2
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf = pypdfium2.PdfDocument.new()
            pdf.new_page(595.28, 841.89)
            pdf.new_page(595.28, 841.89)
            pdf.save(str(tmp / "a.pdf"))
            Image.new("RGB", (100, 140), "white").save(tmp / "b.png")
            paths = page_images([str(tmp / "a.pdf"), str(tmp / "b.png")], tmp / "work")
            self.assertEqual(len(paths), 3)
            self.assertEqual(paths[2], tmp / "b.png")
            self.assertAlmostEqual(min(Image.open(paths[0]).size), 1654, delta=2)

    def test_second_lines_drops_low_scores(self):
        self.assertEqual(second_lines(FakeReader(), Path("x.png")), [{"text": "수업료", "score": 0.98, "box": [1, 2, 3, 4]}])


class PageSignalsTest(unittest.TestCase):
    def test_image_signals_on_sharp_and_blurred(self):
        sharp = image_signals(text_image())
        blurred = image_signals(text_image().filter(ImageFilter.GaussianBlur(4)))
        self.assertGreater(sharp["sharpness"], blurred["sharpness"])
        self.assertEqual(image_signals(Image.new("RGB", (100, 100), "white"))["clipped_share"], 1.0)
        self.assertEqual(sharp["short_side_px"], 400)
        self.assertAlmostEqual(sharp["dpi"], 400 / 8.27, places=1)

    def test_missed_share(self):
        lines = [{"text": "수업료"}, {"text": "3,352,000"}, {"text": "문서확인번호"}, {"text": "계"}]
        self.assertAlmostEqual(missed_share(lines, "수업료3,352,000"), 1 / 3)
        self.assertEqual(missed_share([], "수업료"), 0.0)


if __name__ == "__main__":
    unittest.main()
