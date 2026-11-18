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
    args = parser.parse_args(argv)
    if bool(args.files) == bool(args.from_raw):
        parser.error("give either files or --from-raw")
    applicant = load_applicant(args.applicant)
    if args.from_raw:
        record = json.loads(Path(args.from_raw).read_text(encoding="utf-8"))
    else:
        from ocr_text_basic.read import pipeline, read_document
        record = read_document(args.files, args.doc_id or Path(args.files[0]).stem,
                               pipeline(args.server, args.server_model, args.models_dir))
        if args.raw_out:
            Path(args.raw_out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    doc, masked = build(record, applicant)
    if args.masked_out:
        Path(args.masked_out).write_text(json.dumps(masked, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out = json.dumps(doc, ensure_ascii=False, indent=1)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
