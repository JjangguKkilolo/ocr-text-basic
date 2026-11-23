"""A second PaddleOCR-VL read of the same pages for the two-tier flags (design 2026-11-23). The page is enlarged to 1.25
times the pixels the first read saw: a PDF page is drawn at zoom 2.5 (the first read draws at 2.0) and an image file
is resized by 1.25 with cubic interpolation. The second read is only compared with the first; it never enters the
text and is not written to any output."""
from pathlib import Path

SCALE = 1.25
LABEL = "PaddleOCR-VL x1.25"
PDF_ZOOM = 2.0


def enlarged_pages(paths, work_dir):
    """One enlarged PNG per page, in read_document order."""
    import cv2
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for path in paths:
        path = Path(path)
        if path.suffix.lower() == ".pdf":
            import pypdfium2
            pdf = pypdfium2.PdfDocument(str(path))
            for i in range(len(pdf)):
                target = work_dir / f"{path.stem}.p{i + 1}.png"
                pdf[i].render(scale=PDF_ZOOM * SCALE).to_pil().convert("RGB").save(target)
                out.append(target)
            pdf.close()
        else:
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f"cannot read image: {path}")
            target = work_dir / f"{path.stem}.png"
            cv2.imwrite(str(target), cv2.resize(image, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC))
            out.append(target)
    return out


def second_read_pages(paths, reader, work_dir):
    """The unmasked lines of every page of the second read (plain_pages of its record)."""
    from ocr_text_basic.document import plain_pages
    from ocr_text_basic.read import read_document
    record = read_document([str(p) for p in enlarged_pages(paths, work_dir)], "second_read", reader)
    return plain_pages(record)
