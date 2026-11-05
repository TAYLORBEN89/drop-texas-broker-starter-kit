# Test vectors

All values are synthetic. `vectors.json` is the source; `vectors.csv` is the same field vectors plus composites in CSV
(`field,raw_input,standardized,sha256_base64`; empty standardized/hash means *not hashable*, i.e. null).

- `fields`: one raw input per field rule, with expected standardized value and hash (or null).
- `ndz`: composite records with the four standardized values, the four field hashes, and the composite hash.
- `list_types`: whole records with the expected `email`, `phone` and `ndz` hash for each.

Run everything with `../run-tests.sh`. Runners: `run_js.mjs`, `run_python.py`, `run_cpp.py` (builds `cpp/` with `$CXX`/`g++`), `run_sql.py`,
`compare.py` (JS vs Python vs C++ identical), `fuzz.py` (seeded differential fuzz across all four).
Note: the two ZIP vectors that end in a lone surrogate show it as `\ud835`/`\ud801` in JSON and as U+FFFD in the CSV.
`verify-against-engine.mjs` is a maintainer tool that checks these vectors against the production engine module.

## License

The vector data files (`vectors.json`, `vectors.csv`, `status-response-example.csv`) are licensed under CC BY 4.0
(see `../LICENSE-SPEC`). The runner scripts are Apache-2.0 (see `../LICENSE`).
