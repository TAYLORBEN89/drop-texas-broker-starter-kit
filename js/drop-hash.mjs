// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
// DROP-style normalization and hashing: reference implementation (plain ESM, no dependencies, no build step).
// Runs on Node 18+ and modern browsers (uses WebCrypto). See ../SPEC.md for the rules.

export const STATUS = { 2: 'exempt', 3: 'deleted', 4: 'opted_out', 5: 'not_found' };
export const LIST_TYPES = ['email', 'phone', 'ndz'];
export const RESPONSE_WINDOW_DAYS = 45;

// DROP Transliteration Mapping (CPPA DROP technical spec v1.2.0), plus special Latin letters.
// Letters not in the table are left unchanged.
const GREEK = {
  'α': 'a', 'β': 'v', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'i', 'θ': 'th', 'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm',
  'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't', 'υ': 'y', 'φ': 'f', 'χ': 'ch', 'ψ': 'ps',
  'ω': 'o', 'ά': 'a', 'έ': 'e', 'ί': 'i', 'ή': 'i', 'ύ': 'y', 'ό': 'o', 'ώ': 'o', 'ϊ': 'i', 'ΐ': 'i', 'ϋ': 'y', 'ΰ': 'y',
};
const CYRILLIC = {
  'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
  'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
  'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', 'є': 'e', 'і': 'i', 'ї': 'i',
  'ґ': 'g', 'ў': 'u',
};
const SPECIAL_LATIN = {
  'ß': 'ss', 'æ': 'ae', 'œ': 'oe', 'ø': 'o', 'ð': 'd', 'þ': 'th', 'ł': 'l', 'đ': 'd', 'ħ': 'h', 'ŋ': 'n', 'ı': 'i', 'ĳ': 'ij', 'ŀ': 'l',
};
export const TRANSLIT = { ...GREEK, ...CYRILLIC, ...SPECIAL_LATIN };
const translit = (s) => Array.from(s, (c) => (c in TRANSLIT ? TRANSLIT[c] : c)).join('');

// Names: lowercase, map, fold accents (NFD + drop combining marks), map again, keep only letters and digits.
export function stdName(v) {
  if (v == null) return null;
  let s = translit(String(v).toLowerCase());
  s = translit(s.normalize('NFD').replace(/\p{M}/gu, '')).replace(/[^\p{L}\p{N}]/gu, '');
  return s || null;
}

// Email: trim and lowercase; everything else kept. Must look like local@domain (no whitespace, one @).
export function stdEmail(v) {
  if (v == null) return null;
  const s = String(v).trim().toLowerCase();
  return /^[^\s@]+@[^\s@]+$/.test(s) ? s : null;
}

// Phone: digits only, last 10 (or all if fewer). No digits -> null.
export function stdPhone(v) {
  if (v == null) return null;
  const d = String(v).replace(/\D/g, '');
  return d ? d.slice(-10) : null;
}

// ZIP: drop from first hyphen, keep letters/digits, lowercase, strip leading zeros, first 5. Empty -> null.
export function stdZip(v) {
  if (v == null) return null;
  const s = String(v).split('-')[0].replace(/[^\p{L}\p{N}]/gu, '').toLowerCase().replace(/^0+/, '').slice(0, 5);
  return s || null;
}

// DOB -> YYYYMMDD. Accepts YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD, YYYYMMDD, and US MM/DD/YYYY (or M-D-YYYY).
// Invalid calendar dates, and years below 100, -> null.
export function stdDob(v) {
  if (v == null) return null;
  const s = String(v).trim();
  let y, m, d, g;
  if ((g = s.match(/^(\d{4})[-/.]?(\d{1,2})[-/.]?(\d{1,2})$/)) && (s.length === 8 || /[-/.]/.test(s))) [, y, m, d] = g;
  else if ((g = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/))) [, m, d, y] = g;
  else return null;
  const dt = new Date(Date.UTC(+y, +m - 1, +d));
  if (dt.getUTCFullYear() !== +y || dt.getUTCMonth() !== +m - 1 || dt.getUTCDate() !== +d) return null;
  return `${y}${String(m).padStart(2, '0')}${String(d).padStart(2, '0')}`;
}

const enc = new TextEncoder();
const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');

// SHA-256 over UTF-8, standard Base64 with padding (44 chars).
export async function hashValue(s) {
  return b64(await crypto.subtle.digest('SHA-256', enc.encode(s)));
}

// Hex SHA-256 of a text (used for the manifest checksum of a list file).
export async function sha256Hex(text) {
  return hex(await crypto.subtle.digest('SHA-256', enc.encode(text)));
}

// Composite: concatenate the per-field Base64 hashes (no separator), hash again.
export async function compositeHash(fieldHashes) {
  return hashValue(fieldHashes.join(''));
}

export const STANDARDIZERS = { first_name: stdName, last_name: stdName, dob: stdDob, zip: stdZip, phone: stdPhone, email: stdEmail };

// Hash a record for one list type. Returns null if a required field is missing or not standardizable.
// rec: { first_name, last_name, dob, zip, phone, email }
export async function hashFor(listType, rec) {
  if (listType === 'email') { const e = stdEmail(rec.email); return e && hashValue(e); }
  if (listType === 'phone') { const p = stdPhone(rec.phone); return p && hashValue(p); }
  if (listType === 'ndz') {
    const parts = [stdName(rec.first_name), stdName(rec.last_name), stdDob(rec.dob), stdZip(rec.zip)];
    if (parts.some((p) => !p)) return null;
    return compositeHash(await Promise.all(parts.map(hashValue)));
  }
  throw new Error('unknown list type');
}
