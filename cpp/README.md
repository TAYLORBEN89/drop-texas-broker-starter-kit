# C++ reference

C++17, standard library only (own SHA-256 and Base64). Files: `drop_hash.hpp` (API), `drop_hash.cpp`,
`drop_tables.inc` (generated Unicode tables), `drop_hash_cli.cpp` (line driver used by the test runners),
`generate-tables.mjs` (regenerates the tables from the JS reference), `CMakeLists.txt`.

Build:

```sh
g++ -std=c++17 -O2 -o drop_hash_cli drop_hash.cpp drop_hash_cli.cpp      # plain compiler line (clang++ works too)
cmake -S . -B build && cmake --build build                                # or CMake (library target: drop_hash)
```

```cpp
#include "drop_hash.hpp"
drop::Record r{"Testy", "Example", "01/12/1990", "78701-1234", std::nullopt, std::nullopt};
auto h = drop::hash_for("ndz", r);  // "HkOYp2z1hmlSBntwMGHYOxSjLSxaUxKoPMnTzvGa2G4="
```

How it matches JS exactly: the name rule, the letter/number class, full Unicode lowercasing and the cased /
case-ignorable sets (for the Greek final-sigma rule) come from tables generated from the JS reference
(`drop_tables.inc`, Unicode version recorded in its header). Chinese, Japanese, Korean, Arabic and Hebrew letters
have no table entry, so they pass through unchanged. ZIP truncation counts UTF-16 code units like JavaScript's `slice`, and a lone surrogate is hashed as U+FFFD like
`TextEncoder`.

Limits: input must be UTF-8 (invalid bytes become U+FFFD). Characters newer than the table's Unicode version are
treated as unassigned (dropped from names); regenerate the tables with a newer Node.js to update.
