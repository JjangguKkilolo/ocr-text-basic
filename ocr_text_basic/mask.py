"""Masks identity values in text words. No model call.

A line is split on spaces into words; a masked word becomes [가림] and keeps its place. Three rules, in this order:
1. Layer 1, fixed in code: words matching the application values given (names, ids, birth dates: every key ending in
   birth_date), also when up to MAX_LABEL_CHARS words of one line join into the value with spaces and - . / removed
   (모 의 자 운 길, 2009 03 12), and identity shapes (resident or foreigner number, phone, email, long digit runs other
   than a business registration number written 3-2-5).
2. Kept: amounts, amount headers (경감액) and dates that layer 1 did not take, and the profile's field words, term
   words and item name suffixes (keep_words, keep_term_words, keep_item_suffixes).
3. From profiles/<support type>.yaml: the words after an identity label (identity_labels: 성명, 학번 ...) until a kept
   word, or an amount once a value was masked; the words after a profile label until a kept word; words ending in an
   institution suffix. No profile key can unmask a layer 1 word.
Lines are never joined and positions on the page are not used.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from ocr_text_basic.shared import (MAX_LABEL_CHARS, PATTERNS, amount_header, applicant_hit, dates, flat,
                                   normalize_amount)

MASK = "[가림]"
DATE = re.compile(r"(?:19|20)\d{2}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]\s*\d{1,2}\s*일?")
TERM_DATE = re.compile(r"(?:19|20)\d{2}\s*[./\-]\s*\d{1,2}")
EDGE = ":：|,;()[]"
BUSINESS_NUMBER = re.compile(r"\d{3}-\d{2}-\d{5}")
SHAPES = [(name, rx) for name, rx in PATTERNS if name in ("rrn", "phone", "email")]
PROFILE_KEYS = ("labels", "aliases", "institution_suffixes", "institution_tails", "identity_labels", "keep_words",
                "keep_term_words", "keep_item_suffixes")
PROFILES = Path(__file__).resolve().parent / "profiles"


class Profile:
    def __init__(self, data):
        self.identity_labels = tuple(data.get("identity_labels", []))
        self.labels = tuple(data.get("labels", [])) + tuple(data.get("aliases", []))
        self.keep_words = tuple(data.get("keep_words", []))
        self.term_words = tuple(data.get("keep_term_words", []))
        item = "|".join(map(re.escape, data.get("keep_item_suffixes", [])))
        self.item_word = re.compile(rf"[가-힣]+({item})$") if item else None
        suffixes = data.get("institution_suffixes", [])
        tails = "|".join(map(re.escape, data.get("institution_tails", [])))
        self.institution = re.compile("(" + "|".join(map(re.escape, suffixes)) + r")\d*" +
                                      (f"({tails})?" if tails else "") + "(/.*)?$") if suffixes else None


def load_profile(name="student_aid", text=None):
    """Layer 2 of one support type. Only the PROFILE_KEYS lists are read; any other key (a try to change layer 1 or the
    kept fields) is an error."""
    data = yaml.safe_load(text if text is not None else (PROFILES / f"{name}.yaml").read_text(encoding="utf-8")) or {}
    unknown = set(data) - set(PROFILE_KEYS)
    if unknown:
        raise ValueError(f"profile keys not allowed: {sorted(unknown)}")
    for key, value in data.items():
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ValueError(f"profile key {key} must be a list of words")
    return Profile(data)


@lru_cache(maxsize=None)
def default_profile():
    return load_profile()


def same_value(text, value):
    """Applicant value comparison that also ignores commas: a number written 12,345,678 is the id 12345678."""
    a, b = flat(text).replace(",", ""), flat(value).replace(",", "")
    return len(b) >= 2 and a == b


def clean(word):
    return word.strip(EDGE)


def date_forms(text):
    """Every date of the text as YYYYMMDD and YYMMDD: separated dates (2006년 8월 23일, 2006-08-23) and digit runs of
    eight or six digits that read as a valid date (20060823, 060823)."""
    out = set(dates(text))
    for run in re.findall(r"\d+", re.sub(r"[\s\-./]", "", text or "")):
        for n in (8, 6):
            for at in range(0, len(run) - n + 1):
                part = run[at:at + n]
                full = part if n == 8 else None
                if n == 8 and not part.startswith(("19", "20")):
                    continue
                y, m, d = (part[:4], part[4:6], part[6:]) if n == 8 else (part[:2], part[2:4], part[4:])
                if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                    out.add(part)
                    if full:
                        out.add(full[2:])
    return out


def value_dates(value):
    """The date a whole value states, as YYYYMMDD and YYMMDD, or as YYMMDD alone for a six digit value (060823).
    Empty when the value is not a date (a student id)."""
    out = set(dates(value))
    if out:
        return out
    digits = flat(value)
    if re.fullmatch(r"(19|20)\d{6}", digits) and date_forms(digits) >= {digits}:
        return {digits, digits[2:]}
    if re.fullmatch(r"\d{6}", digits) and digits in date_forms(digits):
        return {digits}
    return set()


def birth_forms(applicant):
    known = set()
    for key, value in (applicant or {}).items():
        if key.endswith("birth_date") and value:
            known |= value_dates(value)
    return known


def birth_hit(text, applicant):
    """A date of the text equal to a birth date of the application data (student and applicant), in any form."""
    known = birth_forms(applicant)
    return bool(known) and bool(known & date_forms(text))


def label_span(words, i, profile):
    """(number of words of a label starting at word i, layer 1 or 2), or (0, None)."""
    joined, first = "", len(clean(words[i]))
    labels = sorted(set(profile.identity_labels) | set(profile.labels), key=len, reverse=True)
    for k, word in enumerate(words[i:], 1):
        if re.search(r"\d", word):
            return 0, None
        joined += clean(word)
        if len(joined) > MAX_LABEL_CHARS:
            return 0, None
        for label in labels:
            # a layer 2 label starts the label (수학과 is a value, not the label 학과); an identity word may follow a
            # short prefix inside the first word (학생성명)
            prefix = 0 if label not in profile.identity_labels else min(first - 1, 2)
            if any(joined.startswith(label, at) for at in range(0, prefix + 1)) and len(joined) <= len(label) + prefix:
                return k, 1 if label in profile.identity_labels else 2
    return 0, None


def institution(word, profile):
    return profile.institution is not None and profile.institution.search(clean(word)) is not None


def field_word(word, profile):
    """A field word the reader needs (profile keep_words); a term word (keep_term_words, 학기) counts at the start of a word or
    after a number (학기, 1학기), so 모래학기기록실 is not one, and a word ending in an institution suffix is a name
    (교육경비재단)."""
    w = clean(word)
    match = profile.institution.search(w) if profile.institution is not None else None
    # a profile suffix cannot turn a fixed field into an institution
    if match and not any(f in match.group(1) for f in profile.keep_words + profile.term_words):
        return False
    return any(f in w for f in profile.keep_words) or any(
        w.startswith(f) or re.search(r"\d\s*" + re.escape(f), w) is not None for f in profile.term_words)


def amount_word(word):
    r = normalize_amount(word)
    return r["amount"] is not None and bool(re.search(r",\d{3}|원$|^[₩￦W]", word))


def kept(word, profile):
    w = clean(word)
    # amount headers (경감액, 납부 금액) are column names the reader needs
    item = profile.item_word is not None and profile.item_word.fullmatch(w) is not None
    return (field_word(w, profile) or item or amount_word(w) or amount_header(w)
            or DATE.search(w) is not None or TERM_DATE.fullmatch(w) is not None)


def shape_of(word):
    """The identity shape of a word (rrn, phone, email, or digits for a long digit run), or None. A word that is exactly
    a business registration number (3-2-5 digits with hyphens) is not one; it is still masked when it equals an
    application value or follows an identity label."""
    for name, rx in SHAPES:
        if rx.search(word):
            return name
    if BUSINESS_NUMBER.fullmatch(clean(word)):
        return None
    # a date written with separators (2026-08-28) is not a long digit run; a birth date is still masked as an
    # application value and after its label
    digits = re.sub(r"[\s\-]", "", DATE.sub(" ", word))
    return "digits" if "," not in word and re.search(r"\d{8,}", digits) is not None else None


def shaped(word):
    return shape_of(word) is not None


def spaced_institutions(words, profile):
    """Indexes of runs of one letter words (경 기 대 학 교) whose joined text, up to MAX_LABEL_CHARS, is an
    institution."""
    hidden, i = set(), 0
    while i < len(words):
        j = i
        while j < len(words) and re.fullmatch(r"[가-힣]", clean(words[j])):
            j += 1
        if j - i >= 2 and j - i <= MAX_LABEL_CHARS and institution("".join(clean(w) for w in words[i:j]), profile):
            hidden |= set(range(i, j))
        i = max(j, i + 1)
    return hidden


def application_field(word, applicant):
    """The application key a word equals or holds, or None."""
    for key, value in (applicant or {}).items():
        if value and same_value(word, value):
            return key
    return applicant_hit(word, applicant) or ("birth_date" if birth_hit(word, applicant) else None)


def layer_one_reason(word, applicant):
    """Why layer 1 masks one word outside any label segment ({"reason": "application", "field"} or {"reason":
    "shape", "shape"}), or None."""
    field = application_field(word, applicant)
    if field:
        return {"reason": "application", "field": field}
    shape = shape_of(word)
    return {"reason": "shape", "shape": shape} if shape else None


def layer_one(word, applicant):
    return layer_one_reason(word, applicant) is not None


def mask_reasons(words, applicant=None, profile=None, cells=None):
    """For every word, why it is masked ({"reason": "application" | "shape" | "label" | "institution", ...}) or None
    when it is kept. cells, when given (a table row masked as one word sequence), is the cell number of every word: a
    label segment ends at the second cell after its label, or at the next cell once it masked a value (so 학번 does not
    also mask 학년 4학년 in the cells after its value). Layer 1 is not touched by it."""
    profile = profile or default_profile()
    spaced = spaced_institutions(words, profile)
    joined = span_fields(words, applicant, MAX_LABEL_CHARS)
    out, i, segment, masked_in, seg_cell, cur_cell, label = [], 0, None, 0, None, None, None
    while i < len(words):
        if segment is not None and cells is not None and cells[i] != cur_cell:
            if masked_in or cells[i] > seg_cell + 1:
                segment = None
            cur_cell = cells[i]
        if i in joined:
            # layer 1 over joined words: a value split into letters or digit groups (모 의 자 운 길, 2009 03 12)
            out.append({"reason": "application", "field": joined[i]})
            masked_in += segment is not None
            i += 1
            continue
        if i in spaced:
            # a spaced institution wins over the label its letters spell (경 기 대 학 교 holds 학 교)
            out.append({"reason": "institution"})
            i += 1
            continue
        one = layer_one_reason(words[i], applicant)
        if one:
            # layer 1 comes before any label: a profile label cannot let a known value through
            out.append(one)
            masked_in += segment is not None
            i += 1
            continue
        span, layer = label_span(words, i, profile)
        if span and any(layer_one(w, applicant) for w in words[i:i + span]):
            span = 0
        if span:
            out += [None] * span
            label = "".join(clean(w) for w in words[i:i + span])
            if cells is not None:
                seg_cell = cur_cell = cells[i + span - 1]
            i += span
            segment, masked_in = layer, 0
            continue
        word = words[i]
        # a layer 1 segment ends at a field word, or at an amount once a value was masked; its first word is masked
        # even when it looks like an amount (학번 12,345,678)
        if segment == 1 and (field_word(word, profile) or (amount_word(word) and masked_in)):
            segment = None
        first = segment == 1 or layer_one(word, applicant)
        keep = not first and kept(word, profile)
        if segment == 2 and keep:
            segment = None
        second = segment == 2 or institution(word, profile)
        hidden = first or (second and not keep)
        masked_in += segment is not None
        out.append(None if not hidden else
                   {"reason": "label", "label": label} if segment in (1, 2) else {"reason": "institution"})
        i += 1
    return out


def mask_words(words, applicant=None, profile=None, cells=None):
    return [MASK if r else w for w, r in zip(words, mask_reasons(words, applicant, profile, cells))]


def span_fields(words, applicant=None, width=4):
    """{index: application key} of words inside a window of up to width words of one line whose joined text is exactly
    an applicant value (spaces and - . / ignored) or a birth date of the application data (a name or a date the OCR
    split into words). Layer 1."""
    hidden = {}
    for i in range(len(words)):
        for k in range(2, width + 1):
            part = words[i:i + k]
            if len(part) < k:
                break
            joined = " ".join(clean(w) for w in part)
            key = next((key for key, v in (applicant or {}).items() if v and same_value(joined, v)), None)
            exact_birth = (DATE.fullmatch(joined) is not None or re.fullmatch(r"[\d\s.\-/]+", joined) is not None) \
                and birth_hit(joined, applicant)
            if key or exact_birth:
                for n in range(i, i + k):
                    hidden.setdefault(n, key or "birth_date")
    return hidden


def mask_spans(words, applicant=None, width=4):
    return set(span_fields(words, applicant, width))


def leaks_in(pages, values):
    """Values (applicant or pii raws) still present in the text to be sent, spaces and separators ignored. A value that
    reads as a date is also found in any other date form of the text (2006년 8월 23일, 060823)."""
    text = "\n".join(p["text"] for p in pages)
    body = flat(text).replace(",", "")
    forms = set()
    for line in text.split("\n"):
        forms |= date_forms(line)
    # a date split over lines or cells (2006/ | 08/ | 23) is one date in the joined text
    forms |= date_forms(text.replace("\n", " "))
    out = []
    for v in values:
        plain = flat(v).replace(",", "")
        if (len(plain) >= 2 and plain in body) or value_dates(v) & forms:
            out.append(v)
    return out
