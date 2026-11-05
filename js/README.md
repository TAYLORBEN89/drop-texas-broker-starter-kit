# JS reference

`drop-hash.mjs` (plain ES module, WebCrypto, no dependencies) and `drop-hash.d.ts` (types). Works in Node 18+ and modern
browsers. Async because WebCrypto digests are async.

Exports: `stdName`, `stdEmail`, `stdPhone`, `stdZip`, `stdDob`, `STANDARDIZERS`, `hashValue`, `compositeHash`,
`hashFor(listType, record)`, `sha256Hex`, `TRANSLIT`, `STATUS`, `LIST_TYPES`, `RESPONSE_WINDOW_DAYS`.
