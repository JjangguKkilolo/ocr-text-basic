"""Whether the cells of an output line are in a second reader's text of the same page (OCR trust signals design,
2026-11-19). A cell is compared by its core characters: letters and digits, and `, . - / :` between two digits (the
CER v2 core rule). A cell with fewer than two core characters is "short" and not judged. Compare unmasked text only;
nothing here is written to the output but the verdicts."""
import unicodedata

CELL_SEP = " | "
LETTERS = ("Lo", "Lu", "Ll", "Lt", "Lm", "Nd")
SEPARATORS = ",.-/:"


def core(text):
    text = "".join(ch for ch in unicodedata.normalize("NFC", text or "") if not ch.isspace() and ch != "|")
    kept = []
    for i, ch in enumerate(text):
        cat = unicodedata.category(ch)
        between = (ch in SEPARATORS and 0 < i < len(text) - 1 and unicodedata.category(text[i - 1]) == "Nd"
                   and unicodedata.category(text[i + 1]) == "Nd")
        if cat in LETTERS or between:
            kept.append(ch)
    return "".join(kept)


def line_cells(line):
    return line.split(CELL_SEP)


def cell_status(cell, other):
    c = core(cell)
    if len(c) < 2:
        return "short"
    return "same" if c in other else "differs"


def line_check(line, other, second_vl=None):
    """{"agree": True|False|None, "cells": [indexes of differing cells]}; None when every cell is short.
    With second_vl (the core text of a second PaddleOCR-VL read of the page; two-tier flags design 2026-11-23) a
    differing line also gets "strong_cells" (cells that differ from both readers) and "level" ("strong" when there is
    such a cell, else "weak"). A cell that differs only from the second read is not flagged."""
    cells = line_cells(line)
    status = [cell_status(c, other) for c in cells]
    differs = [k for k, s in enumerate(status) if s == "differs"]
    if not differs:
        return {"agree": True if "same" in status else None, "cells": []}
    out = {"agree": False, "cells": differs}
    if second_vl is not None:
        strong = [k for k in differs if cell_status(cells[k], second_vl) == "differs"]
        out.update(strong_cells=strong, level="strong" if strong else "weak")
    return out
