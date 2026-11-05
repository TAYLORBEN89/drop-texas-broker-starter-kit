// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
// Example broker client in Node 18+ (no dependencies). Same flow as download_and_match.py.
// node examples/download-and-match.mjs <base-url> <customers.csv> <out-dir>   (token from DROP_BROKER_TOKEN)
import fs from 'node:fs';
import path from 'node:path';
import { hashFor, sha256Hex } from '../js/drop-hash.mjs';

const [base, customersPath, outDir = 'out'] = process.argv.slice(2);
const token = process.env.DROP_BROKER_TOKEN;
if (!base || !customersPath || !token) { console.error('usage: DROP_BROKER_TOKEN=... node download-and-match.mjs <base-url> <customers.csv> [out]'); process.exit(2); }
const auth = { Authorization: `Bearer ${token}` };

// Minimal CSV reader for the sample file (quoted fields supported, no embedded newlines).
function parseCsv(text) {
  const lines = text.split('\n').filter((l) => l && !l.startsWith('#'));
  const split = (l) => { const o = []; let cur = '', q = false; for (const ch of l) { if (ch === '"') q = !q; else if (ch === ',' && !q) { o.push(cur); cur = ''; } else cur += ch; } o.push(cur); return o; };
  const head = split(lines[0]);
  return lines.slice(1).map((l) => Object.fromEntries(split(l).map((v, i) => [head[i], v])));
}
const decide = (m) => (!m.length ? 5 : m.length > 1 ? 4 : m[0].exempt?.toLowerCase() === 'yes' ? 2 : 3);

const customers = parseCsv(fs.readFileSync(customersPath, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const idx = await (await fetch(`${base}/lists`, { headers: auth })).json();
for (const m of idx.lists) {
  const res = await fetch(`${base}/lists/${m.list_id}/file`, { headers: auth });
  const text = await res.text();
  if ((await sha256Hex(text)) !== m.sha256) throw new Error(`checksum mismatch for ${m.list_id}`);
  const index = new Map();
  for (const c of customers) { const h = await hashFor(m.list_type, c); if (h) index.set(h, [...(index.get(h) || []), c]); }
  const rows = text.split('\n').slice(1).filter(Boolean).map((l) => l.split(','));
  const out = 'Id,Status\n' + rows.map(([id, h]) => `${id},${decide(index.get(h) || [])}\n`).join('');
  const file = path.join(outDir, `status_${m.list_id}.csv`);
  fs.writeFileSync(file, out);
  console.log(`${m.list_id}: ${rows.length} rows -> ${file}`);
}
