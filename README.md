# DROP Texas broker integration starter kit

All data in this repository is synthetic. Endpoints and details may change.

Brokers can download lists of hashed opt-out requests that Texans submitted. This kit gives
your engineering (or agent) team everything needed to match those lists against your own records and send statuses
back, without ever receiving raw personal information from us.

The rules follow the California DROP model (11 CCR §7613, CPPA DROP technical specification v1.2.0). If you already
match California DROP lists, expect to reuse most of that work.

## What's inside

| Path | What it is |
| --- | --- |
| [`SPEC.md`](SPEC.md) | Exact normalization and hash rules, with worked examples, list and response formats |
| [`js/`](js/) | Reference implementation, plain ES modules + `.d.ts` types. Node 18+ or a browser; no build, no dependencies |
| [`python/`](python/) | Reference implementation, Python 3.8+ standard library only |
| [`cpp/`](cpp/) | Reference implementation, C++17, standard library only (own SHA-256/Base64), CMake or a plain `g++` line |
| [`sql/`](sql/) | SQLite reference (views + mapping tables) with notes for Postgres; see its README for limits |
| [`test-vectors/`](test-vectors/) | Synthetic vectors (CSV + JSON) and a cross-language runner asserting identical output |
| [`examples/`](examples/) | Download → verify → match → write status CSV, against an included localhost mock server |

## Quickstart

Requirements: Node 18+, Python 3.8+ (its built-in `sqlite3` must be SQLite 3.44+ for the SQL check) and a C++17
compiler (`g++` or `clang++` on PATH, or set `CXX`).

```sh
make test        # or: npm test   or: ./run-tests.sh
make example     # end-to-end demo against the local mock
```

`make test` runs the JS, Python, C++ and SQL implementations over every vector, checks that JS, Python and C++
output is identical, runs a seeded differential fuzz (6,000 inputs across Latin, Greek, Cyrillic, CJK, Hangul, supplementary-plane letters and odd whitespace),
and runs the end-to-end demo.

Use a reference in your own code:

```js
import { hashFor } from './js/drop-hash.mjs';
await hashFor('ndz', { first_name: 'Testy', last_name: 'Example', dob: '01/12/1990', zip: '78701-1234' });
// 'HkOYp2z1hmlSBntwMGHYOxSjLSxaUxKoPMnTzvGa2G4='
```

```python
from drop_hash import hash_for
hash_for("email", {"email": " Testy.Example@Example.com "})
# 'YS5VSxlFrkM6Qv4iurP1Jchz1eykJMIwJmTrVD1a34U='
```

Try the client by hand:

```sh
python3 examples/mock_server.py 8787 &
DROP_BROKER_TOKEN=EXAMPLE-NOT-A-SECRET python3 examples/download_and_match.py \
  --base-url http://127.0.0.1:8787/broker/v1 --customers examples/data/broker-customers.csv --out examples/out --submit
```

## How delivery works

Base URL (placeholder): `https://example.invalid/broker/v1`. You will be given the real one when you are onboarded.

| Method and path | Purpose |
| --- | --- |
| `GET /lists` | Manifests of the lists available to you |
| `GET /lists/{list_id}/manifest` | One manifest |
| `GET /lists/{list_id}/file` | The CSV (`Id,Hash`); headers include `X-Content-SHA256` and `X-List-Version` |
| `POST /lists/{list_id}/link` | A signed download link valid for 5 minutes |
| `POST /lists/{list_id}/status?version={n}` | Upload a status CSV (max 5 MB); returns an acceptance report |

Authentication is a per-broker bearer token (`Authorization: Bearer <token>`), shown once at issue, valid up to 365 days,
and limited to your own lists. Your broker id always comes from the token, never from the request. HTTPS (TLS 1.2+) only.
Lists are never sent by email.

## The 45-day response window

Each list's manifest has `created_at` and `response_due` (Unix seconds). **You have 45 days from `created_at`** to
return a status for every `Id`. A file that arrives after `response_due` is rejected whole and logged. You may send
several partial files before then. New list versions are published monthly.

## Response format

Upload one CSV per list, UTF-8, header `Id,Status`, one row per `Id` from that list:

```
Id,Status
EXAMPLEITEM0001,3
EXAMPLEITEM0002,5
```

| Code | Meaning |
| --- | --- |
| 2 | Exempt: matched, and all personal information held is exempt |
| 3 | Deleted: matched, and the non-exempt personal information was deleted |
| 4 | Opted out: several consumers share the identifier, and all of them were opted out of sale and sharing |
| 5 | Not found: no match after the full matching process |

The response is JSON, for example:
`{"ok": true, "accepted": 2, "rejected": [{"line": 4, "reason": "unknown_id"}], "counts": {"2":0,"3":1,"4":0,"5":1}, "outstanding": 3}`.
Whole-file rejections return HTTP 422 with `ok: false` and a `reason` (`bad_header`, `version_mismatch`, `late`).
An unknown list, or one that is not yours, returns HTTP 404 (the two look the same by design). Row reasons: `malformed`, `unknown_code`, `unknown_id`,
`duplicate_in_file`, `already_recorded`. Statuses are write-once.

## Security notes

- Lists contain only SHA-256 hashes and opaque ids. Hashes of names, dates and ZIPs are guessable by brute force,
  which is why they are only ever sent combined (`ndz`). Treat list files as confidential all the same: store them
  encrypted, restrict access, and delete them once statuses are accepted.
- Keep your token in a secrets manager or an environment variable. Never commit it, log it, or pass it on a shared
  command line. The token in this repo, `EXAMPLE-NOT-A-SECRET`, only works with the local mock.
- Always verify the manifest `sha256` before processing a file.
- The mock server binds to `127.0.0.1` over plain HTTP for local testing only.

## Reporting issues

If any implementation, vector, or SPEC rule disagrees with another, or with hashes you receive, please open an issue
in this repository or email help@droptexas.com. Include the field, the synthetic
input that shows the problem and the outputs you got. **Never include real personal information or a real token.**
For security problems, email help@droptexas.com rather than opening a public issue.

## License

- Code (`js/`, `python/`, `cpp/`, `sql/`, `examples/`, test runners and scripts): Apache License 2.0. See [`LICENSE`](LICENSE)
  and [`NOTICE`](NOTICE).
- Specification and data (`SPEC.md` and the vector data in `test-vectors/`: `vectors.json`, `vectors.csv`,
  `status-response-example.csv`): Creative Commons Attribution 4.0 International (CC BY 4.0). See
  [`LICENSE-SPEC`](LICENSE-SPEC).

Copyright DROP Texas contributors.
