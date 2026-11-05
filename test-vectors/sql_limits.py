# SPDX-License-Identifier: Apache-2.0
# Copyright DROP Texas contributors
"""Inputs the SQL reference does not claim to support (see sql/drop_hash_sqlite.sql)."""
import re


def documented_limit(field, raw):
    """Inputs the SQL version does not claim to support (see the header of drop_hash_sqlite.sql)."""
    if field in ("email", "zip") and re.search(r"[^\x00-\x7f]", raw or ""):
        return True
    if field == "dob" and re.fullmatch(r"\s*[0-9]{4}([-/.][0-9]{3,4}|[0-9]{2,3}[-/.][0-9]{1,2})\s*", raw or ""):
        return True
    if field in ("first_name", "last_name") and name_has_unassigned(raw):
        return True
    return False


def name_has_unassigned(raw):
    import unicodedata
    return any(unicodedata.category(c) == "Cn" for c in raw or "")
