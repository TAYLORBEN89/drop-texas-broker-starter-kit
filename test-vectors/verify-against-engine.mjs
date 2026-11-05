// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
// Maintainer check: compares the kit against a copy of the production hash engine module.
// Usage: node test-vectors/verify-against-engine.mjs /path/to/hashEngine.js [/path/to/upstream-vectors.csv]
// (Not needed by brokers; the engine is not part of this kit.)
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import * as K from '../js/drop-hash.mjs';
const [enginePath, csvPath] = process.argv.slice(2);
if (!enginePath) { console.error('usage: verify-against-engine.mjs <hashEngine.js> [vectors.csv]'); process.exit(2); }
const E = await import(pathToFileURL(enginePath).href);
const std = { first_name: 'stdName', last_name: 'stdName', dob: 'stdDob', zip: 'stdZip', phone: 'stdPhone', email: 'stdEmail' };
const here = new URL('.', import.meta.url);
const V = JSON.parse(fs.readFileSync(new URL('vectors.json', here), 'utf8'));
let n = 0; const bad = [];
const check = (label, a, b) => { n++; if (a !== b) bad.push(`${label}: engine=${a} kit=${b}`); };
for (const v of V.fields) {
  const s = E[std[v.field]](v.input);
  check(`${v.field} ${JSON.stringify(v.input)} std`, s, v.standardized);
  check(`${v.field} ${JSON.stringify(v.input)} hash`, s ? await E.hashValue(s) : null, v.hash);
}
for (const t of V.list_types) for (const k of ['email', 'phone', 'ndz']) check(`record ${k}`, await E.hashFor(k, t.record), t[k]);
const vecN = n;
// Differential: same seeded fuzz inputs the cross-language runner uses, if present.
const fz = new URL('out/fuzz-inputs.json', here);
if (fs.existsSync(fz)) for (const v of JSON.parse(fs.readFileSync(fz, 'utf8'))) {
  check(`fuzz ${v.field} ${JSON.stringify(v.input)}`, E[std[v.field]](v.input), K.STANDARDIZERS[v.field](v.input));
}
const fuzzN = n - vecN;
// Upstream published vectors (field,raw_input,standardized,sha256_base64), computed independently with openssl.
let up = 0;
if (csvPath) for (const line of fs.readFileSync(csvPath, 'utf8').split('\n')) {
  const m = line.match(/^(\w+),"(.*)",([^,]*),([A-Za-z0-9+/=]{44})$/); if (!m) continue;
  up++;
  if (m[1] === 'ndz') { const [f, l, d, z] = m[2].split('|'); check(`upstream ndz`, await K.hashFor('ndz', { first_name: f, last_name: l, dob: d, zip: z }), m[4]); continue; }
  const s = K.STANDARDIZERS[m[1]](m[2]);
  check(`upstream ${m[1]} ${m[2]} std`, s, m[3]); check(`upstream ${m[1]} ${m[2]} hash`, await K.hashValue(s), m[4]);
}
console.log(`engine: ${vecN} vector checks, ${fuzzN} fuzz checks, ${up} upstream CSV rows -> ${bad.length} mismatches`);
for (const b of bad.slice(0, 20)) console.log('  MISMATCH', b);
process.exit(bad.length ? 1 : 0);
