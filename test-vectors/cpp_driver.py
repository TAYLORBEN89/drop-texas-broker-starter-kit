# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Builds (if needed) and drives the C++ reference through cpp/drop_hash_cli."""
import os, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BIN = os.path.join(HERE, "out", "drop_hash_cli")


def build():
    srcs = [os.path.join(ROOT, "cpp", f) for f in ("drop_hash.cpp", "drop_hash_cli.cpp", "drop_hash.hpp", "drop_tables.inc")]
    if os.path.exists(BIN) and all(os.path.getmtime(s) < os.path.getmtime(BIN) for s in srcs):
        return BIN
    cxx = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++") or shutil.which("c++")
    if not cxx:
        return None
    os.makedirs(os.path.dirname(BIN), exist_ok=True)
    subprocess.run([cxx, "-std=c++17", "-O2", "-o", BIN, srcs[0], srcs[1]], check=True)
    return BIN


def _h(v):
    return "-" if v is None else "x" + v.encode("utf-8").hex()


def _unh(s):
    return None if s == "-" else bytes.fromhex(s[1:]).decode("utf-8", "surrogatepass")


def run(binary, fields=(), records=()):
    """fields: [(field, input)] -> [(standardized, hash)]; records: [dict] -> [(email, phone, ndz)]."""
    lines = ["F %s %s" % (f, _h(v)) for f, v in fields]
    lines += ["R " + " ".join(_h(r.get(k)) for k in ("first_name", "last_name", "dob", "zip", "phone", "email")) for r in records]
    out = subprocess.run([binary], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True).stdout.split("\n")
    res_f, res_r = [], []
    for i in range(len(fields)):
        parts = out[i].split(" ")
        res_f.append((_unh(parts[0]), None if parts[1] == "-" else parts[1]))
    for j in range(len(records)):
        res_r.append(tuple(None if x == "-" else x for x in out[len(fields) + j].split(" ")))
    return res_f, res_r
