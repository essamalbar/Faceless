"""Deny-list content moderation for user-supplied free text (inputs-only).

Screens create-endpoint inputs against a word-boundary, case-insensitive
deny-list before any generation runs. The seed list is deliberately small
and conservative — a handful of unambiguous prohibited-category terms,
focused on sexual content involving minors — NOT a broad slur dictionary.

Operators extend it at runtime by pointing FACELESS_MODERATION_DENYLIST at a
newline-delimited file of additional terms (blank lines and `#` comments are
ignored); those union with the seed. The file is read per call so an operator
edit takes effect without a restart — inputs-only screening is low volume, so
the cost is negligible.

Matched terms are surfaced on ModerationError.terms for the caller to LOG (a
count, never the text); they are never echoed back to the end user.

stdlib only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Conservative seed. Unambiguous prohibited-category terms only. Extend at
# runtime via FACELESS_MODERATION_DENYLIST rather than growing this list.
DENYLIST: frozenset[str] = frozenset(
    {
        "child porn",
        "child pornography",
        "childporn",
        "child sexual abuse material",
        "csam",
        "pedophilia",
        "paedophilia",
    }
)


def _load_denylist() -> frozenset[str]:
    """The active deny-list: the seed unioned with any operator file terms.

    Resolved on every call (no module-level cache) so operator edits to the
    FACELESS_MODERATION_DENYLIST file — and test monkeypatches — take effect
    immediately.
    """
    terms: set[str] = set(DENYLIST)
    path = os.environ.get("FACELESS_MODERATION_DENYLIST")
    if path:
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError:
            content = ""
        for line in content.splitlines():
            term = line.strip()
            if term and not term.startswith("#"):
                terms.add(term)
    return frozenset(terms)


def find_violations(text: str | None) -> list[str]:
    """Return the deny-list terms that appear in `text` on a word boundary.

    Case-insensitive. A term embedded inside a larger word (e.g. a term that
    is a substring of an innocent word) does NOT match. Empty / None text
    yields an empty list.
    """
    if not text:
        return []
    hits: list[str] = []
    for term in _load_denylist():
        if re.search(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE):
            hits.append(term)
    return hits


class ModerationError(Exception):
    """Raised when text trips the deny-list. Carries the matched `.terms` so
    the caller can log a COUNT — never the terms or the text — to the user."""

    def __init__(self, terms: list[str]) -> None:
        self.terms = terms
        super().__init__(f"content matched {len(terms)} prohibited term(s)")


def assert_clean(*texts: str | None) -> None:
    """Raise ModerationError if any provided text trips the deny-list.

    None / empty texts are skipped. Matched terms are aggregated (deduped,
    first-seen order) across all inputs onto the raised error.
    """
    hits: list[str] = []
    for text in texts:
        for term in find_violations(text):
            if term not in hits:
                hits.append(term)
    if hits:
        raise ModerationError(hits)
