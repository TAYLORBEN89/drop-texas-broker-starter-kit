// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
// Checks js/drop-hash.mjs against vectors.json and writes out/js.json for the cross-language comparison.
import fs from 'node:fs';
import * as H from '../js/drop-hash.mjs';
const here = new URL('.', import.meta.url);
const V = JSON.parse(fs.readFileSync(new URL('vectors.json', here), 'utf8'));
const out = { fields: [], records: [] };
let pass = 0; const fails = [];
for (const v of V.fields) {
  const s = H.STANDARDIZERS[v.field](v.input);
  const h = s ? await H.hashValue(s) : null;
  out.fields.push({ field: v.field, input: v.input, standardized: s, hash: h });
  if (s === v.standardized && h === v.hash) pass++; else fails.push(`${v.field} ${JSON.stringify(v.input)}: got ${s} ${h}`);
}
for (const t of V.list_types) {
  const got = { email: await H.hashFor('email', t.record), phone: await H.hashFor('phone', t.record), ndz: await H.hashFor('ndz', t.record) };
  out.records.push(got);
  for (const k of ['email', 'phone', 'ndz']) if (got[k] === t[k]) pass++; else fails.push(`record ${k}: got ${got[k]} want ${t[k]}`);
}
fs.mkdirSync(new URL('out/', here), { recursive: true });
fs.writeFileSync(new URL('out/js.json', here), JSON.stringify(out, null, 1));
console.log(`js:     ${pass} passed, ${fails.length} failed`);
for (const f of fails) console.log('  FAIL', f);
process.exit(fails.length ? 1 : 0);
