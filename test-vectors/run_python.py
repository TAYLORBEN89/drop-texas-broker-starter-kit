# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Checks python/drop_hash.py against vectors.json and writes out/python.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import drop_hash as H  # noqa: E402

V = json.load(open(os.path.join(HERE, "vectors.json"), encoding="utf-8"))
out = {"fields": [], "records": []}
passed, fails = 0, []
for v in V["fields"]:
    s = H.STANDARDIZERS[v["field"]](v["input"])
    h = H.hash_value(s) if s else None
    out["fields"].append({"field": v["field"], "input": v["input"], "standardized": s, "hash": h})
    if s == v["standardized"] and h == v["hash"]:
        passed += 1
    else:
        fails.append("%s %r: got %s %s" % (v["field"], v["input"], s, h))
for t in V["list_types"]:
    got = {k: H.hash_for(k, t["record"]) for k in ("email", "phone", "ndz")}
    out["records"].append(got)
    for k in ("email", "phone", "ndz"):
        if got[k] == t[k]:
            passed += 1
        else:
            fails.append("record %s: got %s want %s" % (k, got[k], t[k]))
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "out", "python.json"), "w", encoding="utf-8"), ensure_ascii=True, indent=1)
print("python: %d passed, %d failed" % (passed, len(fails)))
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
