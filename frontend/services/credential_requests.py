"""Bounded phrase matching for explicit credential requests in synthetic text."""

import re

_REQUEST = re.compile(
    r"\b(?:ask\s+for|request(?:\s+for)?|send|share|read|tell|give|enter(?:ing)?|type|provide|confirm|reply\s+with)\b"
    r"(?:[\s\w-]{0,40}?)\b(?:pin|otp|code|password|secret)\b",
    re.IGNORECASE,
)
_NEGATED_PREFIX = re.compile(
    r"\b(?:do\s+not|don't|never|will\s+not|won't|does\s+not|doesn't|should\s+not|shouldn't)\b"
    r"(?:\s+ever)?(?:\s+\w+){0,2}\s*$",
    re.IGNORECASE,
)


def has_explicit_credential_request(text: str) -> bool:
    """Detect a positive request without letting a separate warning negate it."""
    value = str(text or "")
    if re.search(r"\bfa\s+wo\s+pin\b", value, re.IGNORECASE):
        return True
    clauses = re.split(r"[,;.!?\n]+|\b(?:but|however|yet)\b", value, flags=re.IGNORECASE)
    for clause in clauses:
        for match in _REQUEST.finditer(clause):
            if not _NEGATED_PREFIX.search(clause[:match.start()]):
                return True
    return False
