// SPDX-License-Identifier: Apache-2.0
// Copyright DROP Texas contributors
//
// DROP-style normalization and hashing: C++17 reference implementation (standard library only).
// Produces byte-identical output to js/drop-hash.mjs. Inputs and outputs are UTF-8 std::string. See ../SPEC.md.
#pragma once
#include <optional>
#include <string>
#include <vector>

namespace drop {

using Opt = std::optional<std::string>;

struct Record {
  Opt first_name, last_name, dob, zip, phone, email;
};

constexpr int RESPONSE_WINDOW_DAYS = 45;

// Standardizers: return std::nullopt when the value is missing or not hashable.
Opt std_name(const Opt& v);
Opt std_email(const Opt& v);
Opt std_phone(const Opt& v);
Opt std_zip(const Opt& v);
Opt std_dob(const Opt& v);
// Field name -> standardizer ("first_name", "last_name", "dob", "zip", "phone", "email"); throws on unknown.
Opt standardize(const std::string& field, const Opt& v);

// SHA-256 over the UTF-8 bytes, standard Base64 with padding (44 chars).
std::string hash_value(const std::string& s);
// Hex SHA-256 (manifest checksum of a list file).
std::string sha256_hex(const std::string& s);
// Concatenate field hashes (no separator) and hash again.
std::string composite_hash(const std::vector<std::string>& field_hashes);
// list_type: "email", "phone" or "ndz". nullopt when a required field is missing; throws on unknown type.
Opt hash_for(const std::string& list_type, const Record& rec);

}  // namespace drop
