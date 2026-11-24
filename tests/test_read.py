"""read_document keeps block boxes, page sizes and file numbers. No model is loaded."""
import unittest

from ocr_text_basic.read import read_document


class FakeResult:
    def __init__(self, res):
        self.json = {"res": res}


class FakeVL:
    def __init__(self, by_file):
        self.by_file = by_file

    def predict(self, path):
        return self.by_file[path]


def page(width, height, bbox):
    block = {"block_label": "text", "block_content": "x", "block_order": 1}
    if bbox is not None:
        block["block_bbox"] = bbox
    res = {"parsing_res_list": [block]}
    if width is not None:
        res.update(width=width, height=height)
    return FakeResult(res)


class ReadTest(unittest.TestCase):
    def test_pages_keep_file_numbers_sizes_and_block_boxes(self):
        vl = FakeVL({"a.pdf": [page(800, 1000, [10, 20, 300, 60]), page(800, 1000, [0, 0, 5, 5])],
                     "b.png": [page(400, 300, [1, 2, 3, 4])]})
        record = read_document(["a.pdf", "b.png"], "d1", vl)
        self.assertEqual([(p["page"], p["file"], p["file_page"]) for p in record["pages"]], [(1, 1, 1), (2, 1, 2), (3, 2, 1)])
        self.assertEqual((record["pages"][0]["width"], record["pages"][0]["height"]), (800, 1000))
        self.assertEqual((record["pages"][2]["width"], record["pages"][2]["height"]), (400, 300))
        self.assertEqual(record["pages"][0]["blocks"][0]["bbox"], [10, 20, 300, 60])
        self.assertEqual(record["pages"][0]["blocks"][0]["label"], "text")

    def test_missing_size_or_box_becomes_none(self):
        vl = FakeVL({"a.png": [page(None, None, None)]})
        p = read_document(["a.png"], "d1", vl)["pages"][0]
        self.assertIsNone(p["width"])
        self.assertIsNone(p["height"])
        self.assertIsNone(p["blocks"][0]["bbox"])


if __name__ == "__main__":
    unittest.main()
