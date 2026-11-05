# Examples

- `mock_server.py`: localhost-only mock of `/broker/v1` (plain HTTP, token `EXAMPLE-NOT-A-SECRET`, in-memory state,
  real validation rules). Lists are built from `data/mock-requests.csv`.
- `download_and_match.py` (Python) and `download-and-match.mjs` (Node): list → download → verify sha256 → hash your
  customers → match → write `status_<list_id>.csv`; the Python one can `--submit`.
- `data/broker-customers.csv`: a synthetic customer file showing a case-insensitive email match, a phone with a leading
  country code, a hyphenated name, two customers sharing one identifier (status 4), an exempt customer (status 2), and
  a Greek name matching its Latin transliteration.
- `run_demo.py`: runs it all and asserts the results.
