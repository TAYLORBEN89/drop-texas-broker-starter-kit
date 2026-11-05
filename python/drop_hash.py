# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""DROP-style normalization and hashing: reference implementation (Python 3.8+, standard library only).

Produces byte-identical output to js/drop-hash.mjs. See ../SPEC.md for the rules.
"""
import base64
import bisect
import hashlib
import re
import unicodedata

try:
    from ._unchanged_ranges import UNCHANGED_RANGES
except ImportError:
    from _unchanged_ranges import UNCHANGED_RANGES

_UNCHANGED_STARTS = [a for a, _ in UNCHANGED_RANGES]

STATUS = {2: "exempt", 3: "deleted", 4: "opted_out", 5: "not_found"}
LIST_TYPES = ("email", "phone", "ndz")
RESPONSE_WINDOW_DAYS = 45

# DROP Transliteration Mapping (CPPA DROP technical spec v1.2.0), plus special Latin letters.
TRANSLIT = {
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i", "θ": "th",
    "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps",
    "ω": "o", "ά": "a", "έ": "e", "ί": "i", "ή": "i", "ύ": "y", "ό": "o", "ώ": "o",
    "ϊ": "i", "ΐ": "i", "ϋ": "y", "ΰ": "y", "а": "a", "б": "b", "в": "v", "г": "g",
    "д": "d", "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "є": "e", "і": "i", "ї": "i",
    "ґ": "g", "ў": "u", "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ð": "d", "þ": "th",
    "ł": "l", "đ": "d", "ħ": "h", "ŋ": "n", "ı": "i", "ĳ": "ij", "ŀ": "l",}

# Whitespace exactly as JavaScript's String.prototype.trim() and regex \s define it (Python's differ slightly).
_JS_WS = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_EMAIL = re.compile("[^@" + re.escape(_JS_WS) + "]+@[^@" + re.escape(_JS_WS) + "]+")
_DOB_YMD = re.compile(r"([0-9]{4})[-/.]?([0-9]{1,2})[-/.]?([0-9]{1,2})")
_DOB_MDY = re.compile(r"([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{4})")


def _translit(s):
    return "".join(TRANSLIT.get(c, c) for c in s)


def _is_letter_or_digit(c):
    cat = unicodedata.category(c)
    return cat[0] == "L" or cat[0] == "N"


def _unchanged(c):
    """True for Chinese, Japanese, Korean, Arabic and Hebrew characters (left unchanged per the CPPA DROP spec)."""
    cp = ord(c)
    i = bisect.bisect_right(_UNCHANGED_STARTS, cp) - 1
    return i >= 0 and cp <= UNCHANGED_RANGES[i][1]


def _fold(c):
    return "".join(d for d in unicodedata.normalize("NFD", c) if not unicodedata.category(d).startswith("M"))


def std_name(v):
    """Lowercase, map, fold accents (NFD + drop combining marks) except in the unchanged scripts, map again,
    keep letters and digits only."""
    if v is None:
        return None
    s = _translit(str(v).lower())
    s = "".join(c if _unchanged(c) else _fold(c) for c in s)
    s = "".join(c for c in _translit(s) if _is_letter_or_digit(c))
    return s or None


def std_email(v):
    """Trim and lowercase; everything else kept. Must look like local@domain."""
    if v is None:
        return None
    s = str(v).strip(_JS_WS).lower()
    return s if _EMAIL.fullmatch(s) else None


def std_phone(v):
    """Digits only (ASCII 0-9), last 10, or all if fewer. No digits -> None."""
    if v is None:
        return None
    d = re.sub(r"[^0-9]", "", str(v))
    return d[-10:] if d else None


def std_zip(v):
    """Drop from first hyphen, keep letters/digits, lowercase, strip leading zeros, first 5. Empty -> None."""
    if v is None:
        return None
    s = str(v).split("-")[0]
    s = _js_slice(_js_lower("".join(c for c in s if _is_letter_or_digit(c))).lstrip("0"), 5)
    return s or None


def _js_lower(s):
    return s.lower()


def _js_slice(s, n):
    """JavaScript s.slice(0, n): counts UTF-16 code units. A supplementary-plane character cut in half leaves its
    high surrogate, exactly as JS does (hash_value then encodes it as U+FFFD, like TextEncoder)."""
    out, units = [], 0
    for c in s:
        w = 2 if ord(c) > 0xFFFF else 1
        if units + w > n:
            if units < n:
                out.append(chr(0xD800 + ((ord(c) - 0x10000) >> 10)))
            break
        out.append(c)
        units += w
    return "".join(out)


def _valid_date(y, m, d):
    # Matches the JS reference: years below 100 are rejected (JS Date maps them to 19xx).
    if y < 100 or not 1 <= m <= 12 or d < 1:
        return False
    dim = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d <= dim[m - 1]


def std_dob(v):
    """-> YYYYMMDD. Accepts YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD, YYYYMMDD and US MM/DD/YYYY. Invalid -> None."""
    if v is None:
        return None
    s = str(v).strip(_JS_WS)
    g = _DOB_YMD.fullmatch(s)
    if g and (len(s) == 8 or re.search(r"[-/.]", s)):
        y, m, d = g.groups()
    else:
        g = _DOB_MDY.fullmatch(s)
        if not g:
            return None
        m, d, y = g.groups()
    if not _valid_date(int(y), int(m), int(d)):
        return None
    return "%s%02d%02d" % (y, int(m), int(d))


def hash_value(s):
    """SHA-256 over UTF-8, standard Base64 with padding (44 chars)."""
    # Lone surrogates (possible only from _js_slice) become U+FFFD, as with JavaScript's TextEncoder.
    s = "".join("\ufffd" if 0xD800 <= ord(c) <= 0xDFFF else c for c in s)
    return base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode("ascii")


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def composite_hash(field_hashes):
    return hash_value("".join(field_hashes))


STANDARDIZERS = {"first_name": std_name, "last_name": std_name, "dob": std_dob, "zip": std_zip, "phone": std_phone, "email": std_email}


def hash_for(list_type, rec):
    """Hash a record dict for one list type; None if a required field is missing or not standardizable."""
    if list_type == "email":
        e = std_email(rec.get("email"))
        return e and hash_value(e)
    if list_type == "phone":
        p = std_phone(rec.get("phone"))
        return p and hash_value(p)
    if list_type == "ndz":
        parts = [std_name(rec.get("first_name")), std_name(rec.get("last_name")), std_dob(rec.get("dob")), std_zip(rec.get("zip"))]
        if not all(parts):
            return None
        return composite_hash([hash_value(p) for p in parts])
    raise ValueError("unknown list type")
