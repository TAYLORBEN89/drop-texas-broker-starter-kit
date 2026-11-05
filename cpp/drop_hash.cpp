// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
#include "drop_hash.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <regex>
#include <stdexcept>

namespace drop {
namespace {

struct CpStr { char32_t cp; const char* s; };
struct CpRange { char32_t lo, hi; };
#include "drop_tables.inc"  // generated from the JS reference by generate-tables.mjs

// Code points >= 0x110000 never occur; 0xD800..0xDFFF is used internally for a JS lone high surrogate (see std_zip).
template <size_t N>
const char* find_map(const CpStr (&t)[N], char32_t cp) {
  auto it = std::lower_bound(std::begin(t), std::end(t), cp, [](const CpStr& e, char32_t c) { return e.cp < c; });
  return (it != std::end(t) && it->cp == cp) ? it->s : nullptr;
}
template <size_t N>
bool in_ranges(const CpRange (&t)[N], char32_t cp) {
  auto it = std::upper_bound(std::begin(t), std::end(t), cp, [](char32_t c, const CpRange& r) { return c < r.lo; });
  return it != std::begin(t) && cp <= (it - 1)->hi;
}

// UTF-8 -> code points. Invalid sequences become U+FFFD (inputs from JS strings are always valid).
std::u32string decode(const std::string& s) {
  std::u32string out;
  size_t i = 0, n = s.size();
  while (i < n) {
    unsigned char c = s[i];
    char32_t cp; int len;
    if (c < 0x80) { cp = c; len = 1; }
    else if ((c >> 5) == 6) { cp = c & 0x1f; len = 2; }
    else if ((c >> 4) == 14) { cp = c & 0x0f; len = 3; }
    else if ((c >> 3) == 30) { cp = c & 0x07; len = 4; }
    else { out.push_back(0xfffd); i++; continue; }
    if (i + len > n) { out.push_back(0xfffd); i++; continue; }
    bool ok = true;
    for (int k = 1; k < len; k++) {
      unsigned char cc = s[i + k];
      if ((cc >> 6) != 2) { ok = false; break; }
      cp = (cp << 6) | (cc & 0x3f);
    }
    if (!ok) { out.push_back(0xfffd); i++; continue; }
    out.push_back(cp);
    i += len;
  }
  return out;
}

// Code points -> UTF-8. A lone surrogate is written as WTF-8 (ED xx xx) so callers can see it;
// hash_value replaces it with U+FFFD, matching JavaScript's TextEncoder.
void put(std::string& o, char32_t cp) {
  if (cp < 0x80) o += char(cp);
  else if (cp < 0x800) { o += char(0xc0 | (cp >> 6)); o += char(0x80 | (cp & 0x3f)); }
  else if (cp < 0x10000) { o += char(0xe0 | (cp >> 12)); o += char(0x80 | ((cp >> 6) & 0x3f)); o += char(0x80 | (cp & 0x3f)); }
  else { o += char(0xf0 | (cp >> 18)); o += char(0x80 | ((cp >> 12) & 0x3f)); o += char(0x80 | ((cp >> 6) & 0x3f)); o += char(0x80 | (cp & 0x3f)); }
}
std::string encode(const std::u32string& s) { std::string o; for (char32_t c : s) put(o, c); return o; }

// JavaScript String.prototype.toLowerCase (full Unicode mapping incl. the Final_Sigma context rule).
std::u32string js_lower(const std::u32string& s) {
  std::u32string out;
  for (size_t i = 0; i < s.size(); i++) {
    char32_t c = s[i];
    if (c == 0x3a3) {
      bool before = false, after = false;
      for (size_t j = i; j-- > 0;) { if (in_ranges(CASE_IGNORABLE, s[j])) continue; before = in_ranges(CASED, s[j]); break; }
      for (size_t j = i + 1; j < s.size(); j++) { if (in_ranges(CASE_IGNORABLE, s[j])) continue; after = in_ranges(CASED, s[j]); break; }
      out.push_back(before && !after ? 0x3c2 : 0x3c3);
      continue;
    }
    if (const char* m = find_map(LOWER_MAP, c)) out += decode(m); else out.push_back(c);
  }
  return out;
}

// Whitespace as JavaScript's trim() and regex \s define it.
bool js_space(char32_t c) {
  static const std::array<char32_t, 25> ws = {9, 10, 11, 12, 13, 32, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004,
                                              0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000, 0xfeff};
  return std::find(ws.begin(), ws.end(), c) != ws.end();
}
std::u32string js_trim(const std::u32string& s) {
  size_t a = 0, b = s.size();
  while (a < b && js_space(s[a])) a++;
  while (b > a && js_space(s[b - 1])) b--;
  return s.substr(a, b - a);
}

// ---------- SHA-256 (FIPS 180-4) ----------
constexpr std::array<uint32_t, 64> K = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
    0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

std::array<uint8_t, 32> sha256(const std::string& msg) {
  std::array<uint32_t, 8> h = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  std::string m = msg;
  uint64_t bits = uint64_t(msg.size()) * 8;
  m += char(0x80);
  while (m.size() % 64 != 56) m += char(0);
  for (int i = 7; i >= 0; i--) m += char((bits >> (i * 8)) & 0xff);
  for (size_t off = 0; off < m.size(); off += 64) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++)
      w[i] = (uint32_t(uint8_t(m[off + 4 * i])) << 24) | (uint32_t(uint8_t(m[off + 4 * i + 1])) << 16) |
             (uint32_t(uint8_t(m[off + 4 * i + 2])) << 8) | uint32_t(uint8_t(m[off + 4 * i + 3]));
    for (int i = 16; i < 64; i++) {
      uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
      uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
      w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (int i = 0; i < 64; i++) {
      uint32_t t1 = hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
      uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
      hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }
  std::array<uint8_t, 32> out{};
  for (int i = 0; i < 8; i++)
    for (int j = 0; j < 4; j++) out[4 * i + j] = uint8_t(h[i] >> (24 - 8 * j));
  return out;
}

std::string base64(const uint8_t* p, size_t n) {
  static const char* A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string o;
  for (size_t i = 0; i < n; i += 3) {
    uint32_t v = uint32_t(p[i]) << 16 | (i + 1 < n ? uint32_t(p[i + 1]) << 8 : 0) | (i + 2 < n ? p[i + 2] : 0);
    o += A[(v >> 18) & 63];
    o += A[(v >> 12) & 63];
    o += i + 1 < n ? A[(v >> 6) & 63] : '=';
    o += i + 2 < n ? A[v & 63] : '=';
  }
  return o;
}

bool letter_or_number(char32_t c) { return in_ranges(LETTER_OR_NUMBER, c); }

}  // namespace

Opt std_name(const Opt& v) {
  if (!v) return std::nullopt;
  std::string o;
  for (char32_t c : decode(*v)) {
    if (in_ranges(NAME_DROP, c)) {
    } else if (const char* m = find_map(NAME_MAP, c)) {
      o += m;
    } else {
      put(o, c);
    }
  }
  if (o.empty()) return std::nullopt;
  return o;
}

Opt std_email(const Opt& v) {
  if (!v) return std::nullopt;
  std::u32string s = js_lower(js_trim(decode(*v)));
  size_t at = 0, pos = 0;
  for (size_t i = 0; i < s.size(); i++) {
    if (js_space(s[i])) return std::nullopt;
    if (s[i] == U'@') { at++; pos = i; }
  }
  if (at != 1 || pos == 0 || pos + 1 == s.size()) return std::nullopt;
  return encode(s);
}

Opt std_phone(const Opt& v) {
  if (!v) return std::nullopt;
  std::string d;
  for (char c : *v) if (c >= '0' && c <= '9') d += c;
  if (d.empty()) return std::nullopt;
  return d.size() > 10 ? d.substr(d.size() - 10) : d;
}

Opt std_zip(const Opt& v) {
  if (!v) return std::nullopt;
  std::string head = v->substr(0, v->find('-'));
  std::u32string kept;
  for (char32_t c : decode(head)) if (letter_or_number(c)) kept.push_back(c);
  std::u32string s = js_lower(kept);
  size_t z = 0;
  while (z < s.size() && s[z] == U'0') z++;
  // JS slice(0, 5) counts UTF-16 code units; a supplementary character cut in half leaves its high surrogate.
  std::u32string out;
  int units = 0;
  for (size_t i = z; i < s.size(); i++) {
    int w = s[i] > 0xffff ? 2 : 1;
    if (units + w > 5) { if (units < 5) out.push_back(0xd800 + ((s[i] - 0x10000) >> 10)); break; }
    out.push_back(s[i]);
    units += w;
  }
  if (out.empty()) return std::nullopt;
  return encode(out);
}

Opt std_dob(const Opt& v) {
  if (!v) return std::nullopt;
  std::string s = encode(js_trim(decode(*v)));
  static const std::regex ymd("^([0-9]{4})[-/.]?([0-9]{1,2})[-/.]?([0-9]{1,2})$");
  static const std::regex mdy("^([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{4})$");
  std::smatch g;
  std::string y, m, d;
  // JS checks s.length (UTF-16 units); an all-ASCII match makes that equal to the byte length.
  if (std::regex_match(s, g, ymd) && (s.size() == 8 || s.find_first_of("-/.") != std::string::npos)) {
    y = g[1]; m = g[2]; d = g[3];
  } else if (std::regex_match(s, g, mdy)) {
    m = g[1]; d = g[2]; y = g[3];
  } else {
    return std::nullopt;
  }
  int yi = std::stoi(y), mi = std::stoi(m), di = std::stoi(d);
  bool leap = (yi % 4 == 0 && yi % 100 != 0) || yi % 400 == 0;
  static const int dim[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  if (yi < 100 || mi < 1 || mi > 12 || di < 1 || di > dim[mi - 1] + (mi == 2 && leap)) return std::nullopt;
  char buf[8];
  std::snprintf(buf, sizeof buf, "%02d%02d", mi, di);
  return y + buf;
}

Opt standardize(const std::string& field, const Opt& v) {
  if (field == "first_name" || field == "last_name") return std_name(v);
  if (field == "dob") return std_dob(v);
  if (field == "zip") return std_zip(v);
  if (field == "phone") return std_phone(v);
  if (field == "email") return std_email(v);
  throw std::invalid_argument("unknown field");
}

std::string hash_value(const std::string& s) {
  std::string clean;  // WTF-8 lone surrogates (ED A0..BF xx) -> U+FFFD, as TextEncoder does
  for (size_t i = 0; i < s.size(); i++) {
    if (uint8_t(s[i]) == 0xed && i + 2 < s.size() && uint8_t(s[i + 1]) >= 0xa0) { clean += "\xef\xbf\xbd"; i += 2; }
    else clean += s[i];
  }
  auto h = sha256(clean);
  return base64(h.data(), h.size());
}

std::string sha256_hex(const std::string& s) {
  auto h = sha256(s);
  static const char* X = "0123456789abcdef";
  std::string o;
  for (uint8_t b : h) { o += X[b >> 4]; o += X[b & 15]; }
  return o;
}

std::string composite_hash(const std::vector<std::string>& field_hashes) {
  std::string j;
  for (const auto& h : field_hashes) j += h;
  return hash_value(j);
}

Opt hash_for(const std::string& list_type, const Record& r) {
  if (list_type == "email") { auto e = std_email(r.email); return e ? Opt(hash_value(*e)) : std::nullopt; }
  if (list_type == "phone") { auto p = std_phone(r.phone); return p ? Opt(hash_value(*p)) : std::nullopt; }
  if (list_type == "ndz") {
    Opt parts[4] = {std_name(r.first_name), std_name(r.last_name), std_dob(r.dob), std_zip(r.zip)};
    std::vector<std::string> hs;
    for (auto& p : parts) { if (!p) return std::nullopt; hs.push_back(hash_value(*p)); }
    return composite_hash(hs);
  }
  throw std::invalid_argument("unknown list type");
}

}  // namespace drop
