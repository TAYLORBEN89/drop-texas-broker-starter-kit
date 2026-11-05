# DROP Texas broker list matching: normalization and hash specification

> All examples are synthetic.
>
> SPDX-License-Identifier: CC-BY-4.0. This document is licensed under Creative Commons Attribution 4.0 International (see LICENSE-SPEC).

This is the exact rule set the DROP Texas service uses to hash consumer identifiers. It follows the California DROP
model (11 CCR §7613 and the CPPA DROP technical specification v1.2.0), so an existing DROP integration should be
reusable. If you apply these rules to your own records, your hashes will equal ours byte for byte.

The reference implementations in `js/`, `python/`, `cpp/` and `sql/` implement this document, and `test-vectors/` proves they
agree. Where this text and the test vectors ever disagree, treat it as a bug and report it (see README).

## 1. List types

| List type | Hash input | Kind |
| --- | --- | --- |
| `email` | standardized email | single field |
| `phone` | standardized phone | single field |
| `ndz` | first name + last name + DOB + ZIP | composite (section 4) |

Name, DOB and ZIP are never sent on their own. If a required field is missing or cannot be standardized (the rule
returns *null*), that record cannot match that list type. Skip it; never hash an empty string.

## 2. Standardization

Inputs are Unicode strings. "Letter" means Unicode general category L*, "digit/number" means N*, "combining mark"
means M*.

### 2.1 First name and last name (separate fields)

Applied in this order:

1. Lowercase (full Unicode lowercase).
2. Replace each character found in the transliteration table (2.6).
3. Canonical decomposition (NFD), then delete every combining mark. This folds accents: `é`→`e`, `å`→`a`, `ñ`→`n`.
   Skip this step for Chinese, Japanese, Korean, Arabic and Hebrew characters (Unicode scripts Han, Bopomofo,
   Hiragana, Katakana, Hangul, Arabic, Hebrew); see below.
4. Apply the transliteration table again (for base letters exposed by step 3).
5. Delete every character that is not a letter or a number: spaces, hyphens, apostrophes, periods, symbols, emoji.
6. Empty result → null.

Compound names become one value (`Juan Pablo` → `juanpablo`).

Chinese, Japanese, Korean, Arabic and Hebrew characters are left unchanged, as the CPPA DROP "Working with the data"
page says ("Leave Chinese, Japanese, Korean, Arabic, and Hebrew characters unchanged."). They are not decomposed,
accent-folded or transliterated: Hangul syllables stay precomposed (`한국` stays U+D55C U+AD6D), kana keep their
voicing marks (`が` stays `が`), and compatibility ideographs and presentation forms are not normalized. Lowercasing
does not affect them. Step 5 still removes spaces, punctuation and standalone combining marks (for example Arabic
harakat or Hebrew niqqud). The CPPA page publishes no example in these scripts; the test vectors include synthetic ones.

### 2.2 Date of birth → `YYYYMMDD`

Accepted inputs (surrounding whitespace is trimmed; separators may be `-`, `/` or `.`):

- `YYYY-MM-DD` (month and day may be 1 or 2 digits), and `YYYYMMDD` (exactly 8 digits);
- US order `MM/DD/YYYY` (1 or 2 digit month and day). **A date that ends with the year is always month/day/year.**

The date must exist on the calendar (`02/29/2001` → null) and the year must be ≥ 100. Anything else → null.
Output is the 4-digit year, then 2-digit month and day.

### 2.3 ZIP

1. If there is a hyphen, drop it and everything after it (ZIP+4).
2. Keep only letters and digits.
3. Lowercase.
4. Remove leading zeros.
5. Keep the first 5 characters.
6. Empty result (including an all-zero ZIP) → null.

Edge case, kept for exact compatibility with our engine: step 5 counts UTF-16 code units (JavaScript `slice`). A
character outside the Basic Multilingual Plane counts as two, and if the cut falls inside one, only its first half (a
lone surrogate) remains; that unit is hashed as U+FFFD (EF BF BD), as JavaScript's `TextEncoder` does. Real ZIP and
postal codes never contain such characters; the references reproduce it anyway (vectors `1234𝐀`, `𐐀𐐀𐐀`).

### 2.4 Phone

Delete every character that is not an ASCII digit 0–9. Keep the **last 10 digits**, or all digits if there are fewer
than 10. No digits → null.

### 2.5 Email

Trim surrounding whitespace and lowercase. Nothing else changes: `.` and `+` are kept. The result must have exactly
one `@`, with at least one character on each side and no whitespace; otherwise null.

### 2.6 Transliteration table

The CPPA DROP Transliteration Mapping v1.2.0, applied character by character (lowercase keys):

- **Greek:** α→a β→v γ→g δ→d ε→e ζ→z η→i θ→th ι→i κ→k λ→l μ→m ν→n ξ→x ο→o π→p ρ→r σ→s ς→s τ→t υ→y φ→f χ→ch
  ψ→ps ω→o; ά→a έ→e ί→i ή→i ύ→y ό→o ώ→o ϊ→i ΐ→i ϋ→y ΰ→y.
- **Cyrillic:** а→a б→b в→v г→g д→d е→e ё→yo ж→zh з→z и→i й→y к→k л→l м→m н→n о→o п→p р→r с→s т→t у→u ф→f
  х→kh ц→ts ч→ch ш→sh щ→shch ъ→(removed) ы→y ь→(removed) э→e ю→yu я→ya є→e і→i ї→i ґ→g ў→u.
- **Special Latin letters:** ß→ss æ→ae œ→oe ø→o ð→d þ→th ł→l đ→d ħ→h ŋ→n ı→i ĳ→ij ŀ→l.
- Letters the table does not list (for example ђ ј љ њ ћ џ) are left unchanged.

Machine-readable copies: `TRANSLIT` in `js/drop-hash.mjs` and `python/drop_hash.py`, and table `drop_translit` in
`sql/drop_tables.sql`.

## 3. Hashing

- SHA-256 over the UTF-8 bytes of the standardized value.
- Output: standard Base64 (RFC 4648 §4, alphabet `A–Z a–z 0–9 + /`) **with** `=` padding. Always 44 characters.

Reference: `printf %s 'juanpablo' | openssl dgst -sha256 -binary | base64` → `91hIbrbzNeqHs3o81O5yNrXUj7wDd2shvZ6THKi9qz8=`
(this also matches the CPPA DROP published example). The kit also reproduces the CPPA page's other published
examples, including the NDZ composite `PQOfn1RffEKmqMmNAzDKKaoZCwxWbQZkQzPWmQo9REA=`.

## 4. Composite key (`ndz`)

1. Standardize and hash first name, last name, DOB and ZIP separately (all four must be non-null).
2. Concatenate the four Base64 strings in the order **FirstName + LastName + DOB + ZIP**, no separators (176 chars).
3. SHA-256 that string (UTF-8) and Base64-encode it.

## 5. Worked examples (synthetic)

| Field | Raw input | Standardized | SHA-256 / Base64 |
| --- | --- | --- | --- |
| first_name | `Juan Pablo` | `juanpablo` | `91hIbrbzNeqHs3o81O5yNrXUj7wDd2shvZ6THKi9qz8=` |
| last_name | `O'Connor-López` | `oconnorlopez` | `wRhK2NSl7s5y9KV3LUYofirbKMVFXQB04RsLM00gbiI=` |
| last_name | `Strauß` | `strauss` | `K90pL8r/YxCbdHAMrwSKj2vvqU3gBEC+d+PsVWAftpA=` |
| first_name | `Νίκος` | `nikos` | `M1xU87YGGwuLseP9/0x3HDaAyqaNEpnDb9fgj33PZH8=` |
| last_name | `Щербаков` | `shcherbakov` | `nuuqPWr/14clJiqZc3R3AsF7RWr766aj1SiWA3Uj8O0=` |
| dob | `01/12/1990` | `19900112` | `Qzs+CDJkSiNw2NDie4BNMNUh2SApKDrYqNUF2vQiYHc=` |
| zip | `91790-3771` | `91790` | `2FPZucR4x7U8KlM+SFAX4LPGhwNz/PIZUCSUdDh0o/s=` |
| zip | `M1B 1A1` | `m1b1a` | `n8L9q8mVeT6Xt9/EeUNiTukGDrkbPJ3DvOEx14uElxk=` |
| zip | ` 00300-9999` | `300` | `mDvWFLta/s5as7YCP3EUfNe2vCMU+dJ690IlQcZVg4k=` |
| phone | `+1 (512) 555-0100` | `5125550100` | `A4GpifSCgglBOHA6U0xbrtr2Cprvj3aHTC1xFJ6ZV1Y=` |
| phone | `765-4321` | `7654321` | `/miiH8druns6PY5FTsqM0ljeaP0I3d8DXyPdvc5vwEk=` |
| email | ` Testy.Example@Example.com ` | `testy.example@example.com` | `YS5VSxlFrkM6Qv4iurP1Jchz1eykJMIwJmTrVD1a34U=` |

**Composite** for first `Testy`, last `Example`, DOB `01/12/1990`, ZIP `78701-1234`:

```
testy    -> KPVVh7HkLPFEwVucPznPXgTiD7h5eFIlr9YuTfqVH0Q=
example  -> UNhY4JhezH9gQYqvDMWrWH9CwlcKiECVqejMrND2VFw=
19900112 -> Qzs+CDJkSiNw2NDie4BNMNUh2SApKDrYqNUF2vQiYHc=
78701    -> OEJIsYBVd31pQDtHnXThCpbsxsbdbwIwhoTT2U6qytE=
SHA-256/Base64 of the 176-char concatenation -> HkOYp2z1hmlSBntwMGHYOxSjLSxaUxKoPMnTzvGa2G4=
```

## 6. List file format

- UTF-8 CSV, LF line endings, header `Id,Hash`, rows sorted by `Id` in ascending byte order.
- `Id` is an opaque, random work-item id, unique within the list; it carries no meaning and does not link across lists.
  When several of our requests share a hash, the list carries it once under one `Id`; return one status for it.
- One file = one list type for one broker. File name: `droptx_<broker_id>-<list_type>-v<version>_<YYYYMMDD>.csv`.
- Every list has a JSON manifest: `list_id`, `broker_id`, `list_type`, `version`, `created_at` and `response_due`
  (Unix seconds), `row_count`, `file_name`, `sha256` (hex SHA-256 of the exact CSV bytes), `hash`
  (`SHA-256/UTF-8/Base64`), `status_codes`, `response_window_days`. **Verify `sha256` before processing.**
- A published version never changes; the next list for the same broker and type gets the next version number.

## 7. Status responses you send back

CSV, header `Id,Status`, one row per `Id`:

| Code | Meaning |
| --- | --- |
| 2 | Exempt: matched, and all personal information held is exempt |
| 3 | Deleted: matched, and the non-exempt personal information was deleted |
| 4 | Opted out: several consumers share the identifier, and all of them were opted out of sale and sharing |
| 5 | Not found: no match after the full matching process |

Validation: the **whole file** is rejected for a wrong header, unknown list, version mismatch, a list that is not
yours, or arrival after `response_due`. A **single row** is rejected if malformed, its code is not 2/3/4/5, its `Id` is
not in the list, it repeats within the file, or that `Id` already has a status. Statuses are final and recorded once;
partial files are allowed before the deadline. Each upload returns counts and the line numbers of rejected rows.
See `test-vectors/status-response-example.csv`.

## 8. Response window

You have **45 days** from a list's `created_at` to return statuses (`response_due` in the manifest). New list versions
are published monthly.
