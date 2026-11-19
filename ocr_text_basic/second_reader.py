"""PP-OCRv5 as a second reader for the trust signals (design 2026-11-19). Its lines are only compared with the
PaddleOCR-VL output; they never enter the text. A line scoring under 0.5 is dropped; the score is not used as accuracy."""
from pathlib import Path

DPI = 200
MIN_SCORE = 0.5


def page_images(paths, work_dir):
    """One image per page in read_document order: a PDF page drawn at 200 dpi, an image file as it is."""
    import pypdfium2
    work_dir = Path(work_dir)
    out = []
    for path in paths:
        path = Path(path)
        if path.suffix.lower() == ".pdf":
            work_dir.mkdir(parents=True, exist_ok=True)
            pdf = pypdfium2.PdfDocument(str(path))
            for i in range(len(pdf)):
                target = work_dir / f"{path.stem}.p{i + 1}.png"
                pdf[i].render(scale=DPI / 72).to_pil().convert("RGB").save(target)
                out.append(target)
            pdf.close()
        else:
            out.append(path)
    return out


def second_pipeline():
    from paddleocr import PaddleOCR
    return PaddleOCR(text_detection_model_name="PP-OCRv5_mobile_det", text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
                     use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
                     text_det_limit_side_len=1600, text_det_limit_type="max")


def second_lines(reader, image):
    res = list(reader.predict(str(image)))[0].json["res"]
    return [{"text": t, "score": round(float(s), 3), "box": [int(v) for v in b]}
            for t, s, b in zip(res["rec_texts"], res["rec_scores"], res["rec_boxes"]) if float(s) >= MIN_SCORE and t.strip()]
