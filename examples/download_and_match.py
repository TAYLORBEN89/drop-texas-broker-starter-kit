# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Example broker client: download every list, verify it, match it against your customer file, write status CSVs.

Python 3.8+, standard library only.

  python3 examples/download_and_match.py --base-url http://127.0.0.1:8787/broker/v1 \
      --token EXAMPLE-NOT-A-SECRET --customers examples/data/broker-customers.csv --out examples/out [--submit]

Against the real service use https://example.invalid/broker/v1 (placeholder: use the URL you are given) and your own
credential from an environment variable, never from code or a command-line history file.

Status decision used by this example (adapt to your own deletion workflow):
  no customer matches the hash           -> 5 not found
  one customer matches, flagged exempt   -> 2 exempt
  one customer matches                   -> 3 deleted   (only after you have actually deleted)
  several customers share the identifier -> 4 opted out (only after all of them are opted out of sale/sharing)
"""
import argparse, csv, hashlib, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import drop_hash as H  # noqa: E402


def call(url, token, method="GET", body=None):
    req = urllib.request.Request(url, method=method, data=body, headers={"Authorization": "Bearer " + token})
    if body is not None:
        req.add_header("Content-Type", "text/csv")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def load_customers(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def decide(matches):
    if not matches:
        return 5
    if len(matches) > 1:
        return 4
    return 2 if matches[0].get("exempt", "").lower() == "yes" else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--token", default=os.environ.get("DROP_BROKER_TOKEN"))
    ap.add_argument("--customers", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--submit", action="store_true", help="POST the status files back")
    a = ap.parse_args()
    if not a.token:
        sys.exit("set --token or DROP_BROKER_TOKEN")
    base = a.base_url.rstrip("/")
    customers = load_customers(a.customers)
    os.makedirs(a.out, exist_ok=True)

    code, _, body = call(base + "/lists", a.token)
    if code != 200:
        sys.exit("list index failed: HTTP %d %s" % (code, body[:200]))
    summary = []
    for m in json.loads(body)["lists"]:
        code, headers, raw = call("%s/lists/%s/file" % (base, m["list_id"]), a.token)
        if code != 200:
            sys.exit("download failed for %s: HTTP %d" % (m["list_id"], code))
        if hashlib.sha256(raw).hexdigest() != m["sha256"]:
            sys.exit("checksum mismatch for %s; do not process" % m["list_id"])
        lines = raw.decode("utf-8").split("\n")
        if lines[0] != "Id,Hash":
            sys.exit("unexpected header in %s" % m["list_id"])
        index = {}
        for c in customers:
            h = H.hash_for(m["list_type"], c)
            if h:
                index.setdefault(h, []).append(c)
        rows = [l.split(",", 1) for l in lines[1:] if l]
        out_rows = [(item_id, decide(index.get(h, []))) for item_id, h in rows]
        path = os.path.join(a.out, "status_%s.csv" % m["list_id"])
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("Id,Status\n" + "".join("%s,%d\n" % r for r in out_rows))
        counts = {k: sum(1 for _, s in out_rows if s == k) for k in (2, 3, 4, 5)}
        entry = {"list_id": m["list_id"], "rows": len(rows), "response_due": m["response_due"], "counts": counts, "file": path}
        if a.submit:
            with open(path, "rb") as f:
                code, _, resp = call("%s/lists/%s/status?version=%d" % (base, m["list_id"], m["version"]), a.token, "POST", f.read())
            entry["upload"] = {"http": code, **json.loads(resp)}
        summary.append(entry)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
