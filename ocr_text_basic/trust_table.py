"""The measured table of the trust signals (design 2026-11-19): per band of page source and missed share, the real
CER of the pages and the real share of wrong lines among agreeing and differing lines, measured on answered virtual
documents (benefit-evidence-review evals/ocr_quality_v1/trust_signals). These are measured rates, not model scores."""
import json
from pathlib import Path

TABLE = Path(__file__).resolve().parent / "profiles" / "trust_table.json"
MISSED_EDGES = (0.05, 0.15)


def band_key(source, missed):
    if missed < MISSED_EDGES[0]:
        part = "<0.05"
    elif missed < MISSED_EDGES[1]:
        part = "0.05-0.15"
    else:
        part = ">=0.15"
    return f"{source}|{part}"


def load_table(path=TABLE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lookup(table, band, agree, level=None):
    """The measured share of wrong lines. level "strong" reads the pooled strong rate and "weak" the band's weak rate
    (table 2026-11-23 on); a table without them gives None."""
    if agree is None:
        return None
    if level == "strong":
        return (table.get("strong") or {}).get("line_error")
    entry = table.get("bands", {}).get(band)
    if not entry:
        return None
    return entry["line_error"].get("weak" if level == "weak" else ("true" if agree else "false"))
