-- SPDX-License-Identifier: Apache-2.0
-- Copyright DROP Texas contributors
-- DROP-style normalization and hashing in SQL. Dialect: SQLite 3.44+ (uses ORDER BY inside group_concat).
--
-- Requires ONE scalar function that SQLite does not ship: sha256_b64(text) -> standard Base64 of SHA-256(UTF-8).
--   * The test runner registers it from Python's standard library (hashlib + base64).
--   * Or load the sqlean "crypto" extension and define it as crypto_encode(crypto_sha256(x), 'base64').
--   * Postgres equivalent (no extension needed on PG 11+): encode(sha256(convert_to(x, 'UTF8')), 'base64').
-- Load drop_tables.sql first (mapping tables).
--
-- Usage: insert raw values into drop_input(field, raw), then SELECT from drop_hashed.
-- Fields: first_name, last_name, dob, zip, phone, email.
--
-- Known limits of the SQL version (the JS and Python references have none of these):
--   * email: lower() in SQLite folds ASCII only, so a non-ASCII uppercase letter in an email is not lowercased.
--   * zip: only ASCII letters/digits are kept.
--   * dob: inputs that mix a separator with no separator (e.g. 1990-0112) are not parsed.
--   * names: code points unassigned in the Unicode version drop_tables.sql was generated with are kept; the
--     references drop them (they are not letters or digits). Very new characters can also differ between runtimes
--     whose Unicode versions differ (true of JS vs Python too).
-- The cross-language runner lists every vector the SQL skips under these limits.

CREATE TABLE IF NOT EXISTS drop_input (id INTEGER PRIMARY KEY, field TEXT NOT NULL, raw TEXT);

DROP VIEW IF EXISTS drop_hashed;
DROP VIEW IF EXISTS drop_std;
CREATE VIEW drop_std AS
WITH RECURSIVE
  ws(w) AS (SELECT char(9,10,11,12,13,32,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288,65279)),
  src AS (
    SELECT i.id, i.field, i.raw,
      CASE WHEN i.field = 'zip' AND instr(i.raw, '-') > 0 THEN substr(i.raw, 1, instr(i.raw, '-') - 1) ELSE i.raw END AS s
    FROM drop_input i WHERE i.raw IS NOT NULL AND i.field IN ('first_name', 'last_name', 'zip', 'phone')),
  chars(id, pos, c, rest) AS (
    SELECT id, 0, '', s FROM src
    UNION ALL
    SELECT id, pos + 1, substr(rest, 1, 1), substr(rest, 2) FROM chars WHERE length(rest) > 0),
  mapped AS (
    SELECT ch.id, ch.pos, s.field,
      CASE
        WHEN s.field IN ('first_name', 'last_name') THEN
          CASE WHEN unicode(ch.c) < 128 THEN (CASE WHEN lower(ch.c) GLOB '[a-z0-9]' THEN lower(ch.c) ELSE '' END)
               WHEN unicode(ch.c) BETWEEN 44032 AND 55203 THEN  -- Hangul syllable: canonical decomposition (NFD)
                 char(4352 + (unicode(ch.c) - 44032) / 588, 4449 + ((unicode(ch.c) - 44032) % 588) / 28)
                 || CASE WHEN (unicode(ch.c) - 44032) % 28 > 0 THEN char(4519 + (unicode(ch.c) - 44032) % 28) ELSE '' END
               WHEN unicode(ch.c) BETWEEN 57344 AND 63743 OR unicode(ch.c) >= 983040 THEN ''  -- private use: dropped
               ELSE coalesce((SELECT n.rep FROM drop_name_char n WHERE n.ch = ch.c), ch.c) END
        WHEN s.field = 'zip' THEN (CASE WHEN lower(ch.c) GLOB '[a-z0-9]' THEN lower(ch.c) ELSE '' END)
        WHEN s.field = 'phone' THEN (CASE WHEN ch.c GLOB '[0-9]' THEN ch.c ELSE '' END)
      END AS r
    FROM chars ch JOIN src s ON s.id = ch.id WHERE ch.pos > 0),
  joined AS (
    SELECT id, field, coalesce(group_concat(r, '' ORDER BY pos), '') AS v FROM mapped GROUP BY id, field),
  perchar AS (
    SELECT s.id, s.field, CASE
      WHEN s.field = 'phone' THEN nullif(substr(coalesce(j.v, ''), -10), '')
      WHEN s.field = 'zip' THEN nullif(substr(ltrim(coalesce(j.v, ''), '0'), 1, 5), '')
      ELSE nullif(coalesce(j.v, ''), '') END AS standardized
    FROM src s LEFT JOIN joined j ON j.id = s.id),
  em AS (
    SELECT i.id, i.field, lower(trim(i.raw, (SELECT w FROM ws))) AS e FROM drop_input i WHERE i.field = 'email' AND i.raw IS NOT NULL),
  email AS (
    SELECT id, field, CASE
      WHEN length(e) - length(replace(e, '@', '')) = 1 AND instr(e, '@') > 1 AND instr(e, '@') < length(e)
       AND e NOT GLOB ('*[' || (SELECT w FROM ws) || ']*') THEN e END AS standardized
    FROM em),
  d0 AS (
    SELECT i.id, i.field, replace(replace(trim(i.raw, (SELECT w FROM ws)), '/', '-'), '.', '-') AS n
    FROM drop_input i WHERE i.field = 'dob' AND i.raw IS NOT NULL),
  d1 AS (
    SELECT id, field, n,
      CASE WHEN instr(n, '-') > 0 THEN substr(n, 1, instr(n, '-') - 1) END AS p1,
      CASE WHEN instr(n, '-') > 0 THEN substr(n, instr(n, '-') + 1) END AS r1
    FROM d0),
  d2 AS (
    SELECT id, field, n, p1,
      CASE WHEN instr(r1, '-') > 0 THEN substr(r1, 1, instr(r1, '-') - 1) END AS p2,
      CASE WHEN instr(r1, '-') > 0 THEN substr(r1, instr(r1, '-') + 1) END AS p3
    FROM d1),
  d3 AS (
    SELECT id, field, CASE
      WHEN n GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN substr(n, 1, 4)
      WHEN length(p1) = 4 AND length(p2) BETWEEN 1 AND 2 AND length(p3) BETWEEN 1 AND 2 THEN p1
      WHEN length(p1) BETWEEN 1 AND 2 AND length(p2) BETWEEN 1 AND 2 AND length(p3) = 4 THEN p3 END AS y,
    CASE
      WHEN n GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN substr(n, 5, 2)
      WHEN length(p1) = 4 AND length(p2) BETWEEN 1 AND 2 AND length(p3) BETWEEN 1 AND 2 THEN p2
      WHEN length(p1) BETWEEN 1 AND 2 AND length(p2) BETWEEN 1 AND 2 AND length(p3) = 4 THEN p1 END AS m,
    CASE
      WHEN n GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN substr(n, 7, 2)
      WHEN length(p1) = 4 AND length(p2) BETWEEN 1 AND 2 AND length(p3) BETWEEN 1 AND 2 THEN p3
      WHEN length(p1) BETWEEN 1 AND 2 AND length(p2) BETWEEN 1 AND 2 AND length(p3) = 4 THEN p2 END AS d
    FROM d2),
  dob AS (
    SELECT id, field, CASE
      WHEN y IS NOT NULL AND (y || m || d) NOT GLOB '*[^0-9]*' AND CAST(y AS INTEGER) >= 100
       AND date(printf('%04d-%02d-%02d', y, m, d)) = printf('%04d-%02d-%02d', y, m, d)
      THEN printf('%s%02d%02d', y, CAST(m AS INTEGER), CAST(d AS INTEGER)) END AS standardized
    FROM d3)
SELECT id, field, standardized FROM perchar
UNION ALL SELECT id, field, standardized FROM email
UNION ALL SELECT id, field, standardized FROM dob;

CREATE VIEW drop_hashed AS
SELECT i.id, i.field, i.raw, s.standardized,
       CASE WHEN s.standardized IS NOT NULL THEN sha256_b64(s.standardized) END AS hash
FROM drop_input i LEFT JOIN drop_std s ON s.id = i.id;

-- Composite (ndz) for consumer records. Insert into drop_record, then SELECT from drop_record_hashes.
CREATE TABLE IF NOT EXISTS drop_record (rec_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, dob TEXT, zip TEXT, phone TEXT, email TEXT);
-- drop_record_input maps each record field into drop_input; refresh it with drop_load_records (see test runner).
CREATE TABLE IF NOT EXISTS drop_record_input (rec_id TEXT NOT NULL, field TEXT NOT NULL, input_id INTEGER NOT NULL);

DROP VIEW IF EXISTS drop_record_hashes;
CREATE VIEW drop_record_hashes AS
WITH h AS (
  SELECT ri.rec_id, ri.field, dh.hash FROM drop_record_input ri JOIN drop_hashed dh ON dh.id = ri.input_id)
SELECT r.rec_id,
  (SELECT hash FROM h WHERE h.rec_id = r.rec_id AND field = 'email') AS email_hash,
  (SELECT hash FROM h WHERE h.rec_id = r.rec_id AND field = 'phone') AS phone_hash,
  CASE WHEN (SELECT count(hash) FROM h WHERE h.rec_id = r.rec_id AND field IN ('first_name', 'last_name', 'dob', 'zip')) = 4
    THEN sha256_b64(
      (SELECT hash FROM h WHERE h.rec_id = r.rec_id AND field = 'first_name') ||
      (SELECT hash FROM h WHERE h.rec_id = r.rec_id AND field = 'last_name') ||
      (SELECT hash FROM h WHERE h.rec_id = r.rec_id AND field = 'dob') ||
      (SELECT hash FROM h WHERE h.rec_id = r.rec_id AND field = 'zip')) END AS ndz_hash
FROM drop_record r;
