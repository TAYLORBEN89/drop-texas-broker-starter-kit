# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""End-to-end demo on localhost: starts the mock, runs the Python client with --submit, then runs the Node client
and checks both clients wrote byte-identical status files. Exits non-zero on any failure."""
import json, os, subprocess, sys, tempfile, threading
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mock_server  # noqa: E402

srv = mock_server.serve(0)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/broker/v1" % port
env = dict(os.environ, DROP_BROKER_TOKEN=mock_server.TOKEN)
cust = os.path.join(HERE, "data", "broker-customers.csv")
py_out, js_out = tempfile.mkdtemp(), tempfile.mkdtemp()
r = subprocess.run([sys.executable, os.path.join(HERE, "download_and_match.py"), "--base-url", base, "--customers", cust,
                    "--out", py_out, "--submit"], env=env, capture_output=True, text=True)
print(r.stdout)
if r.returncode:
    sys.exit(r.stderr)
summary = json.loads(r.stdout)
expected = {"example-broker-email-v1": {2: 1, 3: 1, 4: 0, 5: 4}, "example-broker-phone-v1": {2: 0, 3: 2, 4: 0, 5: 4},
            "example-broker-ndz-v1": {2: 1, 3: 2, 4: 1, 5: 2}}
for e in summary:
    got = {int(k): v for k, v in e["counts"].items()}
    assert got == expected[e["list_id"]], (e["list_id"], got)
    assert e["upload"]["http"] == 200 and e["upload"]["ok"] and e["upload"]["outstanding"] == 0, e["upload"]
# A second upload of the same file must be rejected row by row (statuses are write-once).
r2 = subprocess.run([sys.executable, os.path.join(HERE, "download_and_match.py"), "--base-url", base, "--customers", cust,
                     "--out", py_out, "--submit"], env=env, capture_output=True, text=True)
for e in json.loads(r2.stdout):
    assert e["upload"]["accepted"] == 0 and all(x["reason"] == "already_recorded" for x in e["upload"]["rejected"]), e
subprocess.run(["node", os.path.join(HERE, "download-and-match.mjs"), base, cust, js_out], env=env, check=True)
for f in sorted(os.listdir(py_out)):
    assert open(os.path.join(py_out, f), "rb").read() == open(os.path.join(js_out, f), "rb").read(), f
srv.shutdown()
print("DEMO PASSED: 3 lists matched, uploads accepted, re-upload rejected as already_recorded, Python and Node outputs identical")
