-- SPDX-License-Identifier: Apache-2.0
-- Copyright DROP Texas contributors
-- Copies every drop_record field into drop_input (ids from 1,000,000,000 up) and records the mapping.
-- Run after loading drop_record; re-run whenever drop_record changes.
DELETE FROM drop_input WHERE id IN (SELECT input_id FROM drop_record_input);
DELETE FROM drop_record_input;
CREATE TEMP TABLE IF NOT EXISTS _drop_fields (k INTEGER PRIMARY KEY, f TEXT NOT NULL);
DELETE FROM _drop_fields;
INSERT INTO _drop_fields VALUES (0, 'first_name'), (1, 'last_name'), (2, 'dob'), (3, 'zip'), (4, 'phone'), (5, 'email');
INSERT INTO drop_record_input (rec_id, field, input_id)
  SELECT r.rec_id, x.f, 1000000000 + r.rowid * 8 + x.k FROM drop_record r CROSS JOIN _drop_fields x;
INSERT INTO drop_input (id, field, raw)
  SELECT ri.input_id, ri.field, CASE ri.field
    WHEN 'first_name' THEN r.first_name WHEN 'last_name' THEN r.last_name WHEN 'dob' THEN r.dob
    WHEN 'zip' THEN r.zip WHEN 'phone' THEN r.phone ELSE r.email END
  FROM drop_record_input ri JOIN drop_record r ON r.rec_id = ri.rec_id;
