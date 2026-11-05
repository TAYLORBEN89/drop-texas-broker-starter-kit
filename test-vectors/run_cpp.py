# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Builds and checks the C++ reference (cpp/) against vectors.json; writes out/cpp.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpp_driver  # noqa: E402

binary = cpp_driver.build()
if not binary:
    print("cpp:    FAILED (no C++17 compiler found; set CXX)")
    sys.exit(1)
V = json.load(open(os.path.join(HERE, "vectors.json"), encoding="utf-8"))
rf, rr = cpp_driver.run(binary, [(v["field"], v["input"]) for v in V["fields"]], [t["record"] for t in V["list_types"]])
out = {"fields": [], "records": []}
passed, fails = 0, []
for v, (s, h) in zip(V["fields"], rf):
    out["fields"].append({"field": v["field"], "input": v["input"], "standardized": s, "hash": h})
    if s == v["standardized"] and h == v["hash"]:
        passed += 1
    else:
        fails.append("%s %r: got %r %s" % (v["field"], v["input"], s, h))
for t, got in zip(V["list_types"], rr):
    out["records"].append(dict(zip(("email", "phone", "ndz"), got)))
    for k, g in zip(("email", "phone", "ndz"), got):
        if g == t[k]:
            passed += 1
        else:
            fails.append("record %s: got %s want %s" % (k, g, t[k]))
json.dump(out, open(os.path.join(HERE, "out", "cpp.json"), "w", encoding="utf-8"), ensure_ascii=True, indent=1)
print("cpp:    %d passed, %d failed" % (passed, len(fails)))
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
