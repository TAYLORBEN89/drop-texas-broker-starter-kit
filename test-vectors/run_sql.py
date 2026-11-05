# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Runs sql/drop_hash_sqlite.sql in an in-memory SQLite database (Python stdlib sqlite3, no docker, no CLI)
and checks it against vectors.json. sha256_b64 is registered from hashlib, as documented in the SQL file."""
import base64, hashlib, json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sql_limits import documented_limit  # noqa: E402
SQL = os.path.join(HERE, "..", "sql")

if tuple(map(int, sqlite3.sqlite_version.split("."))) < (3, 44, 0):
    print("sql:    SKIPPED (SQLite %s < 3.44)" % sqlite3.sqlite_version)
    sys.exit(0)

db = sqlite3.connect(":memory:")
db.create_function("sha256_b64", 1, lambda s: None if s is None else base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode(), deterministic=True)
for f in ("drop_tables.sql", "drop_hash_sqlite.sql"):
    db.executescript(open(os.path.join(SQL, f), encoding="utf-8").read())

V = json.load(open(os.path.join(HERE, "vectors.json"), encoding="utf-8"))


for i, v in enumerate(V["fields"], 1):
    db.execute("INSERT INTO drop_input (id, field, raw) VALUES (?, ?, ?)", (i, v["field"], v["input"]))
passed, skipped, fails = 0, [], []
rows = {r[0]: r for r in db.execute("SELECT id, field, standardized, hash FROM drop_hashed")}
for i, v in enumerate(V["fields"], 1):
    _, _, s, h = rows[i]
    if s == v["standardized"] and h == v["hash"]:
        passed += 1
    elif documented_limit(v["field"], v["input"]):
        skipped.append("%s %r" % (v["field"], v["input"]))
    else:
        fails.append("%s %r: got %s %s want %s" % (v["field"], v["input"], s, h, v["standardized"]))
for n, t in enumerate(V["list_types"]):
    r = t["record"]
    db.execute("INSERT INTO drop_record VALUES (?,?,?,?,?,?,?)", ("r%d" % n, r.get("first_name"), r.get("last_name"), r.get("dob"), r.get("zip"), r.get("phone"), r.get("email")))
db.executescript(open(os.path.join(SQL, "load_records.sql"), encoding="utf-8").read())
got = {row[0]: row for row in db.execute("SELECT rec_id, email_hash, phone_hash, ndz_hash FROM drop_record_hashes")}
for n, t in enumerate(V["list_types"]):
    g = got["r%d" % n]
    for k, val in zip(("email", "phone", "ndz"), g[1:]):
        if val == t[k]:
            passed += 1
        else:
            fails.append("record %d %s: got %s want %s" % (n, k, val, t[k]))
print("sql:    %d passed, %d failed, %d skipped (documented SQL limits; SQLite %s)" % (passed, len(fails), len(skipped), sqlite3.sqlite_version))
for s in skipped:
    print("  SKIP", s)
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
