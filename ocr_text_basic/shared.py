"""Small text helpers the masking needs: identity fields and shapes, dates, amount reading and amount headers."""
import re

FIELDS = ("student_name", "student_id", "birth_date", "applicant_name", "employee_id", "phone", "account_number",
          "address", "email")
NAMES = ("student_name", "applicant_name")
MAX_LABEL_CHARS = 8

DATE = re.compile(r"((?:19|20)\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
PATTERNS = (("rrn", re.compile(r"\d{6}\s*-\s*[1-8*][\d*]{0,6}")),
            ("phone", re.compile(r"01[016789]\s*[-.\s]?\s*\d{3,4}\s*[-.\s]?\s*\d{4}")),
            ("birth_date", DATE),
            ("email", re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")))
AMOUNT_SUFFIXES = ("금액", "총액", "합계", "소계", "총계")

# generic header words: a label is a header word when its text without spaces (at most MAX_HEADER_CHARS characters,
# no digit) is one of HEADER_WORDS or ends with one of HEADER_SUFFIXES
ITEM_HEADER_SUFFIXES = ("항목명", "항목", "구분", "내역", "과목", "비목", "내용", "품목", "품명")
HEADER_SUFFIXES = ITEM_HEADER_SUFFIXES + ("금액", "총액", "합계", "소계", "총계", "수량", "단가", "일자", "비고")
HEADER_WORDS = {"계", "고지", "부과", "청구", "납부", "납입", "감면", "장학", "장학금", "실납부액", "수납액", "공제"}
MAX_HEADER_CHARS = 10


def compact(text):
    return re.sub(r"[\s:：]", "", text or "")


def flat(text):
    return re.sub(r"[\s\-./]", "", text or "")


def dates(text):
    out = {f"{y}{int(m):02d}{int(d):02d}" for y, m, d in DATE.findall(text or "")}
    return out | {d[2:] for d in out}


def applicant_hit(text, applicant):
    if not applicant or not text:
        return None
    body = flat(text)
    for field in FIELDS:
        value = applicant.get(field)
        if not value:
            continue
        if field == "birth_date":
            known = dates(value) or {flat(value)}
            if known & (dates(text) | {body}) or any(k in body for k in known if len(k) >= 6):
                return field
            continue
        v = flat(value)
        if len(v) >= 2 and (field in NAMES or len(v) >= 4) and v in body:
            return field
    return None


def header_word(text):
    """(start, end, is_item_header) of the header word inside text, or None."""
    joined = "".join((text or "").split())
    if not joined or len(joined) > MAX_HEADER_CHARS or re.search(r"\d", joined):
        return None
    if joined in HEADER_WORDS:
        start = len(text) - len(text.lstrip())
        return start, start + len(text.strip()), False
    for suffix in sorted(HEADER_SUFFIXES, key=len, reverse=True):
        if joined.endswith(suffix):
            start = text.rfind(suffix)
            span = (start, start + len(suffix)) if start >= 0 else (0, len(text))
            return span[0], span[1], suffix in ITEM_HEADER_SUFFIXES
    return None


def amount_header(text):
    """An amount column header: 2 to 8 characters without a digit ending in 액 (청구액, 납부액), or a header word
    ending in an amount suffix (납부 금액)."""
    flat_text = compact(text)
    if not 2 <= len(flat_text) <= 8 or re.search(r"\d", flat_text):
        return False
    return flat_text.endswith("액") or (bool(header_word(text)) and flat_text.endswith(AMOUNT_SUFFIXES))


GROUPED = re.compile(r"-?\d{1,3}(,\d{3})+")
PLAIN = re.compile(r"-?\d+")
PLACEHOLDERS = {"", "-", "–", "—", "‐"}


def strip_amount(text):
    """Removes outer spaces, a leading currency mark and a trailing 원. Spaces inside the number stay."""
    t = (text or "").strip()
    fixed = False
    if re.match(r"^[₩￦\\]", t):
        t = t[1:].lstrip()
    elif re.match(r"^W\s*\d", t):
        t, fixed = t[1:].lstrip(), True
    return re.sub(r"\s*원$", "", t), fixed


def result(amount, status, reason=None, fixed=False):
    return {"amount": amount, "status": status, "reason": reason, "symbol_fixed": fixed}


def normalize_amount(text, comma_column=False):
    t, fixed = strip_amount(text)
    if not re.search(r"\d", t):
        if t in PLACEHOLDERS:
            return result(None, "ok")
        return result(None, "unreadable", "no_digits")
    if GROUPED.fullmatch(t):
        return result(int(t.replace(",", "")), "ok", None, fixed)
    if PLAIN.fullmatch(t):
        if len(t.lstrip("-")) <= 5:
            return result(int(t), "ok", None, fixed)
        if comma_column:
            return result(int(t), "check_needed", "no_comma_large", fixed)
        return result(None, "not_amount", None, fixed)
    if re.fullmatch(r"-?[\d,]+", t):
        return result(int(t.replace(",", "")), "check_needed", "comma_group", fixed)
    if re.fullmatch(r"-?[\d,\s]+", t):
        return result(int(re.sub(r"[,\s]", "", t)), "check_needed", "inner_space", fixed)
    return result(None, "unreadable", "non_digit", fixed)
