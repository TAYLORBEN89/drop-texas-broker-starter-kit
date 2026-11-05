// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
//
// Line-oriented driver used by the test runners. Values are "x" + hex-encoded UTF-8; "-" means null.
//   in:  F <field> <hex>                         out: <std-hex or -> <hash or ->
//   in:  R <fn> <ln> <dob> <zip> <phone> <email>  out: <email-hash or -> <phone-hash or -> <ndz-hash or ->
#include <iostream>
#include <sstream>
#include "drop_hash.hpp"

static drop::Opt unhex(const std::string& h) {
  if (h == "-") return std::nullopt;
  std::string o;
  for (size_t i = 1; i + 1 < h.size(); i += 2) o += char(std::stoi(h.substr(i, 2), nullptr, 16));
  return o;
}
static std::string hex(const drop::Opt& s) {
  if (!s) return "-";
  static const char* X = "0123456789abcdef";
  std::string o = "x";
  for (unsigned char c : *s) { o += X[c >> 4]; o += X[c & 15]; }
  return o;
}
static std::string or_dash(const drop::Opt& s) { return s ? *s : "-"; }

int main() {
  std::ios::sync_with_stdio(false);
  std::string line;
  while (std::getline(std::cin, line)) {
    std::istringstream in(line);
    std::string kind;
    in >> kind;
    if (kind == "F") {
      std::string field, h;
      in >> field >> h;
      auto s = drop::standardize(field, unhex(h));
      std::cout << hex(s) << ' ' << (s ? drop::hash_value(*s) : "-") << '\n';
    } else if (kind == "R") {
      std::string f[6];
      for (auto& x : f) in >> x;
      drop::Record r{unhex(f[0]), unhex(f[1]), unhex(f[2]), unhex(f[3]), unhex(f[4]), unhex(f[5])};
      std::cout << or_dash(drop::hash_for("email", r)) << ' ' << or_dash(drop::hash_for("phone", r)) << ' '
                << or_dash(drop::hash_for("ndz", r)) << '\n';
    }
  }
}
