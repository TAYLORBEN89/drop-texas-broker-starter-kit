#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Cross-language test: JS (Node 18+), Python 3.8+ (stdlib), C++17 (any g++/clang++; set CXX), SQL (SQLite via Python's sqlite3).
set -e
cd "$(dirname "$0")"
node test-vectors/run_js.mjs
python3 test-vectors/run_python.py
python3 test-vectors/run_cpp.py
python3 test-vectors/compare.py
python3 test-vectors/run_sql.py
python3 test-vectors/fuzz.py
python3 examples/run_demo.py > /dev/null 2>&1 && echo "demo:   end-to-end mock download/match/upload passed"
echo "ALL TESTS PASSED"
