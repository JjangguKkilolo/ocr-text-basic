"""PaddleOCR-VL 1.6 over the pages of one document: the layout blocks of every page, in reading order.

Two ways to run the vision language part:
- default: PaddleOCR's own local inference (the models download on first use);
- server: an OpenAI compatible server already serving the model (on a Mac, mlx_vlm.server with the MLX build); give
  its URL and the model name it serves.
"""
import time
from pathlib import Path

LAYOUT_MODEL = "PP-DocLayoutV3"


def pipeline(server=None, server_model=None, models_dir=None):
    from paddleocr import PaddleOCRVL
    options = {"pipeline_version": "v1.6", "layout_detection_model_name": LAYOUT_MODEL,
               "use_doc_orientation_classify": False, "use_doc_unwarping": False}
    if models_dir:
        options["layout_detection_model_dir"] = str(Path(models_dir) / LAYOUT_MODEL)
    if server:
        if not server_model:
            raise ValueError("--server needs --server-model, the model name the server serves")
        # one request at a time: batched requests to the MLX server sometimes fail on a page with a shape error
        options.update(vl_rec_backend="mlx-vlm-server", vl_rec_server_url=server, vl_rec_api_model_name=server_model,
                       vl_rec_max_concurrency=1)
    return PaddleOCRVL(**options)


def read_document(paths, doc_id, reader):
    """{"doc", "pages": [{"page", "seconds", "file", "file_page", "width", "height", "blocks": [{"label", "content",
    "order", "bbox"}]}]} of the files in order (a PDF gives one page per PDF page; images are one page each). file and
    file_page count from 1; width, height and bbox are the reader's own pixels, None when it gave none."""
    pages = []
    for file_number, path in enumerate(paths, 1):
        started = time.perf_counter()
        results = list(reader.predict(str(path)))
        took = time.perf_counter() - started
        for file_page, r in enumerate(results, 1):
            res = r.json.get("res", r.json)
            pages.append({"page": len(pages) + 1, "seconds": round(took / max(1, len(results)), 2),
                          "file": file_number, "file_page": file_page, "width": res.get("width"), "height": res.get("height"),
                          "blocks": [{"label": b["block_label"], "content": b["block_content"], "order": b.get("block_order"),
                                      "bbox": b.get("block_bbox")}
                                     for b in res.get("parsing_res_list", [])]})
    return {"doc": doc_id, "pages": pages}
