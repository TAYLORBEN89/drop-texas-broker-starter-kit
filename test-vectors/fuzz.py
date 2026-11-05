# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Differential fuzz: 6,000 seeded random inputs (ASCII, punctuation, Latin accents, Greek, Cyrillic, CJK, Hangul,
supplementary-plane letters, odd whitespace) run through the Python, JS, C++ and SQL references; the standardized
values and hashes must agree. SQL is compared only on inputs inside its documented limits."""
import json, os, random, subprocess, sys, sqlite3, base64, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import drop_hash as H  # noqa: E402
sys.path.insert(0, HERE)
from sql_limits import documented_limit  # noqa: E402
import cpp_driver  # noqa: E402

rnd = random.Random(20261104)
POOLS = [
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    " -'.,/+@()_\t\u00a0\u2019\u2010",
    "áàâäãåçéèêëíìîïñóòôöõøúùûüýÿßæœðþłđħŋıĳŀÁÉÍÓÚÑÇ",
    "αβγδεζηθικλμνξοπρσςτυφχψωάέίήύόώϊΐϋΰΑΒΓΔΣΩΆΊ",
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяєіїґўАБВЁЖЩЯЄІЇҐЎђјљњћџ",
    "李王张中文한국어العربيةעברית",
    "\U00010400\U00010428\U0001D400\U0001D7CE\U00020000\u03a3\u0130",
]
inputs = []
for field in ("first_name", "last_name", "dob", "zip", "phone", "email"):
    for _ in range(1000):
        if field == "dob" and rnd.random() < 0.6:
            y, m, d = rnd.randint(1, 2100), rnd.randint(0, 13), rnd.randint(0, 32)
            sep = rnd.choice(["-", "/", ".", ""])
            s = rnd.choice(["%04d%s%02d%s%02d" % (y, sep, m, sep, d), "%d%s%d%s%04d" % (m, sep or "/", d, sep or "/", y)])
        elif field == "email" and rnd.random() < 0.6:
            s = "".join(rnd.choice(rnd.choice(POOLS[:3])) for _ in range(rnd.randint(1, 8))) + "@example.com"
        else:
            s = "".join(rnd.choice(rnd.choice(POOLS)) for _ in range(rnd.randint(0, 12)))
        inputs.append({"field": field, "input": s})
path = os.path.join(HERE, "out", "fuzz-inputs.json")
json.dump(inputs, open(path, "w", encoding="utf-8"), ensure_ascii=False)
js = subprocess.run(["node", "--input-type=module", "-e", """
import fs from 'node:fs'; import * as H from '../js/drop-hash.mjs';
const I = JSON.parse(fs.readFileSync('out/fuzz-inputs.json', 'utf8')); const o = [];
for (const v of I) { const s = H.STANDARDIZERS[v.field](v.input); o.push([s, s ? await H.hashValue(s) : null]); }
process.stdout.write(JSON.stringify(o));"""], cwd=HERE, capture_output=True, text=True, check=True)
jo = json.loads(js.stdout)
db = sqlite3.connect(":memory:")
db.create_function("sha256_b64", 1, lambda s: None if s is None else base64.b64encode(hashlib.sha256(s.encode()).digest()).decode())
for f in ("drop_tables.sql", "drop_hash_sqlite.sql"):
    db.executescript(open(os.path.join(HERE, "..", "sql", f), encoding="utf-8").read())
db.executemany("INSERT INTO drop_input (id, field, raw) VALUES (?,?,?)", [(i, v["field"], v["input"]) for i, v in enumerate(inputs)])
so = {r[0]: (r[1], r[2]) for r in db.execute("SELECT id, standardized, hash FROM drop_hashed")}
cpp_bin = cpp_driver.build()
co, _ = cpp_driver.run(cpp_bin, [(v["field"], v["input"]) for v in inputs])
bad_js, bad_sql, bad_cpp, sql_n = [], [], [], 0
for i, v in enumerate(inputs):
    s = H.STANDARDIZERS[v["field"]](v["input"])
    p = [s, H.hash_value(s) if s else None]
    if p != jo[i]:
        bad_js.append((v, p, jo[i]))
    if p != list(co[i]):
        bad_cpp.append((v, p, co[i]))
    if not documented_limit(v["field"], v["input"]):
        sql_n += 1
        if list(so[i]) != p:
            bad_sql.append((v, p, so[i]))
print("fuzz:   %d inputs, JS vs Python mismatches: %d; JS vs C++ mismatches: %d; SQL compared on %d, mismatches: %d" % (len(inputs), len(bad_js), len(bad_cpp), sql_n, len(bad_sql)))
for b in (bad_js + bad_cpp + bad_sql)[:15]:
    print("  DIFF", b)
sys.exit(1 if bad_js or bad_cpp or bad_sql else 0)
