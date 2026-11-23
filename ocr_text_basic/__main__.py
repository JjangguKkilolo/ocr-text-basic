"""python -m ocr_text_basic FILE [FILE ...] -o out.json --masked-out masked.json [--applicant applicant.json]
    [--server URL --server-model NAME]

Reads the files of one document with PaddleOCR-VL and writes {"document": {"doc_id"}, "pages": [{"page", "text"}]}
with identity values masked as numbered tokens [가림#id]. --masked-out writes the original words and the reason of
every token to a separate file, for code only: do not give that file to an LLM. --from-raw builds the output from
a reader record saved earlier with --raw-out, without loading any model.
"""
import argparse
import json
import sys
from pathlib import Path

from ocr_text_basic.document import build
from ocr_text_basic.shared import FIELDS


def load_applicant(path):
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = [k for k in data if k not in FIELDS and not k.endswith("birth_date")]
    if unknown:
        raise SystemExit(f"applicant keys not known: {unknown}; use {list(FIELDS)} or keys ending in birth_date")
    return {k: str(v) for k, v in data.items() if v}


def check_document(doc, record, paths, vl_reader):
    """page_quality and line_checks: the PP-OCRv5 second reader, a second PaddleOCR-VL read of the enlarged pages with
    vl_reader (two-tier flags design 2026-11-23) and the measured trust table."""
    import tempfile
    from PIL import Image
    from ocr_text_basic.document import checked
    from ocr_text_basic.page_signals import image_signals
    from ocr_text_basic.second_read import second_read_pages
    from ocr_text_basic.second_reader import page_images, second_lines, second_pipeline
    from ocr_text_basic.trust_table import load_table
    sources = []
    for path in paths:
        if Path(path).suffix.lower() == ".pdf":
            import pypdfium2
            pdf = pypdfium2.PdfDocument(str(path))
            sources += ["pdf"] * len(pdf)
            pdf.close()
        else:
            sources.append("image")
    reader = second_pipeline()
    with tempfile.TemporaryDirectory() as tmp:
        images = page_images(paths, Path(tmp))
        second = [second_lines(reader, image) for image in images]
        signals = []
        for image in images:
            with Image.open(image) as im:
                signals.append(image_signals(im))
        second_vl = second_read_pages(paths, vl_reader, Path(tmp) / "vl2")
    return checked(doc, record, second, signals, load_table(), sources, second_vl)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m ocr_text_basic", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="PDF or image files of one document, in page order")
    parser.add_argument("-o", "--output", help="output JSON path (default: print)")
    parser.add_argument("--doc-id", help="document id (default: the first file name without extension)")
    parser.add_argument("--masked-out", help="path for the masked values (original words; keep away from any LLM)")
    parser.add_argument("--applicant", help="JSON file of application values to mask, such as student_name")
    parser.add_argument("--server", help="URL of a server serving PaddleOCR-VL (Mac: mlx_vlm.server)")
    parser.add_argument("--server-model", help="model name the server serves")
    parser.add_argument("--models-dir", help="folder holding a downloaded PP-DocLayoutV3")
    parser.add_argument("--raw-out", help="also save the reader record (unmasked) to this path")
    parser.add_argument("--from-raw", help="build the output from a saved reader record; no model is loaded")
    parser.add_argument("--check", action="store_true",
                        help="add page_quality and line_checks: PP-OCRv5 second reader, a second PaddleOCR-VL read on enlarged "
                             "pages and the measured trust table (with --from-raw also give --server and --server-model)")
    parser.add_argument("--images", nargs="*", help="with --from-raw and --check: the original files, in page order")
    args = parser.parse_args(argv)
    if bool(args.files) == bool(args.from_raw):
        parser.error("give either files or --from-raw")
    applicant = load_applicant(args.applicant)
    reader = None
    if args.from_raw:
        record = json.loads(Path(args.from_raw).read_text(encoding="utf-8"))
    else:
        from ocr_text_basic.read import pipeline, read_document
        reader = pipeline(args.server, args.server_model, args.models_dir)
        record = read_document(args.files, args.doc_id or Path(args.files[0]).stem, reader)
        if args.raw_out:
            Path(args.raw_out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    doc, masked = build(record, applicant)
    if args.check:
        paths = args.files or args.images
        if not paths:
            parser.error("--check needs the files (with --from-raw give them with --images)")
        if reader is None:
            from ocr_text_basic.read import pipeline
            reader = pipeline(args.server, args.server_model, args.models_dir)
        doc = check_document(doc, record, paths, reader)
    if args.masked_out:
        Path(args.masked_out).write_text(json.dumps(masked, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out = json.dumps(doc, ensure_ascii=False, indent=1)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
