# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""LOCAL MOCK of the broker delivery API (/broker/v1). For trying the example client only.

- Binds to 127.0.0.1 only, plain HTTP. The real service is HTTPS-only (TLS 1.2+).
- Accepts one obviously fake bearer token: EXAMPLE-NOT-A-SECRET. Real credentials are issued per broker.
- Builds three hashed lists (email, phone, ndz; version 1) from data/mock-requests.csv using the Python reference.
- Status uploads follow the real validation rules; state is in memory and resets on restart.

Run: python3 examples/mock_server.py [port]    (default 8787)
"""
import csv, io, json, os, re, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import drop_hash as H  # noqa: E402

TOKEN = "EXAMPLE-NOT-A-SECRET"
BROKER_ID = "example-broker"
MAX_STATUS_BYTES = 5 * 1024 * 1024
DAY = 86400


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def build_lists(created_at):
    recs = read_csv(os.path.join(HERE, "data", "mock-requests.csv"))
    lists = {}
    for lt in H.LIST_TYPES:
        hashes = sorted({h for h in (H.hash_for(lt, r) for r in recs) if h})
        items = [("EXAMPLEITEM%s%04d" % (lt.upper(), i + 1), h) for i, h in enumerate(hashes)]
        items.sort()
        body = "Id,Hash\n" + "".join("%s,%s\n" % it for it in items)
        list_id = "%s-%s-v1" % (BROKER_ID, lt)
        lists[list_id] = {
            "manifest": {
                "list_id": list_id, "broker_id": BROKER_ID, "list_type": lt, "version": 1,
                "created_at": created_at, "response_due": created_at + H.RESPONSE_WINDOW_DAYS * DAY,
                "row_count": len(items), "file_name": "droptx_%s_%s.csv" % (list_id, time.strftime("%Y%m%d", time.gmtime(created_at))),
                "sha256": H.sha256_hex(body), "hash": "SHA-256/UTF-8/Base64",
                "status_codes": {str(k): v for k, v in H.STATUS.items()}, "response_window_days": H.RESPONSE_WINDOW_DAYS,
            },
            "csv": body, "ids": {i for i, _ in items}, "status": {},
        }
    return lists


LISTS = build_lists(int(time.time()))


def ingest(lst, version, text, now):
    m = lst["manifest"]
    if m["version"] != version:
        return 422, {"ok": False, "reason": "version_mismatch", "accepted": 0, "rejected": []}
    if now > m["response_due"]:
        return 422, {"ok": False, "reason": "late", "accepted": 0, "rejected": []}
    lines = [l for l in text.replace("\r", "").split("\n") if l]
    if not lines or lines[0] != "Id,Status":
        return 422, {"ok": False, "reason": "bad_header", "accepted": 0, "rejected": []}
    seen, rejected, ok = set(), [], []
    for n, l in enumerate(lines[1:], start=2):
        g = re.fullmatch(r"([A-Za-z0-9_-]{1,64}),([0-9]+)", l)
        if not g:
            rejected.append({"line": n, "reason": "malformed"}); continue
        item, code = g.group(1), int(g.group(2))
        if code not in H.STATUS:
            rejected.append({"line": n, "reason": "unknown_code"}); continue
        if item not in lst["ids"]:
            rejected.append({"line": n, "reason": "unknown_id"}); continue
        if item in seen:
            rejected.append({"line": n, "reason": "duplicate_in_file"}); continue
        seen.add(item)
        if item in lst["status"]:
            rejected.append({"line": n, "reason": "already_recorded"}); continue
        ok.append((item, code))
    counts = {"2": 0, "3": 0, "4": 0, "5": 0}
    for item, code in ok:
        lst["status"][item] = code
        counts[str(code)] += 1
    return 200, {"ok": True, "accepted": len(ok), "rejected": rejected, "counts": counts,
                 "outstanding": len(lst["ids"]) - len(lst["status"])}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", extra=None):
        data = (json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype if ctype != "text/csv" else "text/csv; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        if self.headers.get("Authorization", "") != "Bearer " + TOKEN:
            self._send(401, {"error": "unauthorized"}, extra={"WWW-Authenticate": "Bearer"})
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        if not self._auth():
            return
        if u.path == "/broker/v1/lists":
            return self._send(200, {"lists": [l["manifest"] for l in LISTS.values()]})
        g = re.fullmatch(r"/broker/v1/lists/([a-z0-9_-]{1,80})/(manifest|file)", u.path)
        lst = g and LISTS.get(g.group(1))
        if not lst:
            return self._send(404, {"error": "not found"})
        if g.group(2) == "manifest":
            return self._send(200, lst["manifest"])
        m = lst["manifest"]
        return self._send(200, lst["csv"], "text/csv", {
            "Content-Disposition": 'attachment; filename="%s"' % m["file_name"],
            "X-Content-SHA256": m["sha256"], "X-List-Version": str(m["version"])})

    def do_POST(self):
        u = urlparse(self.path)
        if not self._auth():
            return
        g = re.fullmatch(r"/broker/v1/lists/([a-z0-9_-]{1,80})/status", u.path)
        lst = g and LISTS.get(g.group(1))
        if not lst:
            return self._send(404, {"error": "not found"})
        v = parse_qs(u.query).get("version", [""])[0]
        if not re.fullmatch(r"-?[0-9]+", v):
            return self._send(400, {"error": "bad request"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_STATUS_BYTES:
            return self._send(413, {"error": "too large"})
        code, body = ingest(lst, int(v), self.rfile.read(n).decode("utf-8"), int(time.time()))
        return self._send(code, body)

    def log_message(self, fmt, *args):
        sys.stderr.write("mock: " + fmt % args + "\n")


def serve(port=8787):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return srv


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print("mock broker API on http://127.0.0.1:%d/broker/v1  (token: %s)" % (port, TOKEN))
    serve(port).serve_forever()
