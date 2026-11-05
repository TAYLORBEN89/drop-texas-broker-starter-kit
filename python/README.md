# Python reference

`drop_hash.py`, Python 3.8+, standard library only. Synchronous.

Functions: `std_name`, `std_email`, `std_phone`, `std_zip`, `std_dob`, `STANDARDIZERS`, `hash_value`, `composite_hash`,
`hash_for(list_type, record_dict)`, `sha256_hex`; constants `TRANSLIT`, `STATUS`, `LIST_TYPES`, `RESPONSE_WINDOW_DAYS`.

Whitespace trimming and the email whitespace check use exactly the character set JavaScript's `trim()` and `\s` use,
and digits are ASCII only, so results match the JS reference byte for byte. Unicode letter/number classes come from
`unicodedata`; characters added in Unicode versions newer than your Python's tables may be treated differently.

ZIP truncation counts UTF-16 code units, as JavaScript does (see SPEC 2.3), so supplementary-plane characters
produce the same result as the engine.

Python's `unicodedata` has no Script property, so the code point ranges of the scripts the spec leaves unchanged
(Chinese, Japanese, Korean, Arabic, Hebrew) are generated from the JS reference into `_unchanged_ranges.py`
(`node python/generate-ranges.mjs`).
