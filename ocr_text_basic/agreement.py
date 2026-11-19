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


def line_check(line, other):
    """{"agree": True|False|None, "cells": [indexes of differing cells]}; None when every cell is short."""
    status = [cell_status(c, other) for c in line_cells(line)]
    differs = [k for k, s in enumerate(status) if s == "differs"]
    if differs:
        return {"agree": False, "cells": differs}
    return {"agree": True if "same" in status else None, "cells": []}
