"""Page signals for the trust signals (design 2026-11-19): image measures of the page and the share of second reader
lines the PaddleOCR-VL output does not hold (a likely missed region). These are inputs to a measured table, not
accuracies themselves."""
import numpy as np

from ocr_text_basic.agreement import core

A4_SHORT_INCH = 8.27


def image_signals(image):
    gray = np.asarray(image.convert("L"), dtype=np.float64)
    lap = 4 * gray[1:-1, 1:-1] - gray[:-2, 1:-1] - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:]
    short = min(image.size)
    return {"short_side_px": short, "dpi": round(short / A4_SHORT_INCH, 1), "sharpness": round(float(lap.var()), 1),
            "contrast": round(float(np.percentile(gray, 95) - np.percentile(gray, 5)), 1),
            "clipped_share": round(float((gray >= 250).mean()), 4)}


def missed_share(lines, vl_core):
    judged = [core(l["text"]) for l in lines]
    judged = [c for c in judged if len(c) >= 2]
    if not judged:
        return 0.0
    return sum(1 for c in judged if c not in vl_core) / len(judged)
