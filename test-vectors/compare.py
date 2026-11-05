# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Asserts the JS, Python and C++ outputs are identical (same standardized values and hashes for every vector)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
load = lambda n: json.load(open(os.path.join(HERE, "out", n + ".json"), encoding="utf-8"))
js, py, cpp = load("js"), load("python"), load("cpp")
n = len(js["fields"]) + 3 * len(js["records"])
ok = True
for name, other in (("Python", py), ("C++", cpp)):
    if other != js:
        ok = False
        for x, y in zip(js["fields"], other["fields"]):
            if x != y:
                print("  DIFF", name, x, y)
        print("cross:  JS vs %s DIFFER" % name)
if not ok:
    sys.exit(1)
print("cross:  JS, Python and C++ identical on all %d outputs" % n)
