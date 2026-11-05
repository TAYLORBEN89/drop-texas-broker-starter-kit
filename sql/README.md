# SQL reference (SQLite)

**Dialect:** SQLite 3.44+. Files: `drop_tables.sql` (mapping tables, generated), `drop_hash_sqlite.sql` (views),
`load_records.sql` (helper for the composite view), `generate-tables.mjs` (regenerates `drop_tables.sql` from the JS
reference).

```sql
-- after loading drop_tables.sql and drop_hash_sqlite.sql, with sha256_b64() registered:
INSERT INTO drop_input (field, raw) VALUES ('email', ' Testy.Example@Example.com ');
SELECT standardized, hash FROM drop_hashed;
-- testy.example@example.com | YS5VSxlFrkM6Qv4iurP1Jchz1eykJMIwJmTrVD1a34U=
```

Matching: load your customers into `drop_record`, run `load_records.sql`, load a list into a table `list(id, hash)`,
then `SELECT l.id FROM list l JOIN drop_record_hashes r ON r.ndz_hash = l.hash` (or `email_hash` / `phone_hash`).

## SHA-256 in SQL

SQLite has no built-in SHA-256, so the views call one scalar function, `sha256_b64(text)`:

- the test runner (`test-vectors/run_sql.py`) registers it from Python's `hashlib`;
- or load the sqlean `crypto` extension and wrap `crypto_encode(crypto_sha256(x), 'base64')`;
- most drivers (Python, Go, Node better-sqlite3, JDBC) can register a user function in a few lines.

**Postgres** (11+) needs no extension for the hash: `encode(sha256(convert_to(x, 'UTF8')), 'base64')`. `lower()` is
Unicode-aware there, but Postgres has no NFD-based accent fold that is guaranteed identical, so load `drop_name_char`
and apply it per character exactly as the SQLite view does, or standardize names in application code.

## Honest limits

Pure SQL can't do Unicode normalization or character-class tests, so names use a **precomputed per-character table**
(`drop_name_char`, ~15,000 rows) generated from the JS reference, plus arithmetic Hangul decomposition. That gives
identical output on all vectors and on the differential fuzz, with these exceptions, which the runner reports as
"skipped" if a vector ever hits them:

- email: `lower()` folds ASCII only;
- ZIP: only ASCII letters and digits are kept (so the UTF-16 truncation edge case in SPEC 2.3 does not apply);
- email: Greek final-sigma lowercasing is not applied;
- DOB: inputs that mix a separator with none (e.g. `1990-0112`) are not parsed;
- names: code points unassigned in the table's Unicode version are kept (the references drop them).

For production use we recommend standardizing in application code (JS or Python reference, or a port tested against
`test-vectors/`) and using SQL for the join.
