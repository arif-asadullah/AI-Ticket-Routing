"""PII masking — strip sensitive personal data from ticket text before it is
stored, embedded, or sent to the LLM.

Tickets only need the technical problem ("user can't log in"), never the
person's SSN or card number — so dangerous identifiers are replaced with
redaction tokens at the API boundary. Everything downstream (ArangoDB, vector
index, audit log, LLM prompts, similar-ticket retrieval) only ever sees the
masked text.

Scope is deliberately conservative to avoid mangling technical content:
- SSNs (123-45-6789) — unambiguous format. Fully masked: ***-**-****.
- Payment card numbers (13-19 digits, optionally space/dash separated) —
  validated with the Luhn checksum so ticket IDs, PIDs, ports and log values
  are not false-positived. Masked receipt-style, keeping the last 4 digits
  (**** **** **** 1111) so users can still tell which card was meant.
Masks are shape-preserving (asterisks, original separators kept) so they read
naturally to end users — like a bank statement, not a developer log.
IPs, emails and phone numbers are NOT masked: they are routinely needed to
diagnose and route IT issues.
"""

import re

SSN_TOKEN = "***-**-****"

# 123-45-6789 — the separators make this format unambiguous in IT text
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Candidate card numbers: 13-19 digits, optionally separated by spaces/dashes.
# Candidates are confirmed with Luhn before masking.
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn_valid(digits: str) -> bool:
    """Luhn checksum — true for real payment card numbers."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_card_candidate(match: re.Match) -> str:
    candidate = match.group()
    digits = re.sub(r"[ -]", "", candidate)
    if not (13 <= len(digits) <= 19 and _luhn_valid(digits)):
        return candidate  # not a card (e.g. a long numeric ID) — leave it
    # Receipt-style mask: keep separators and the last 4 digits (**** **** **** 1111)
    masked, digits_left = [], len(digits)
    for ch in candidate:
        if ch.isdigit():
            masked.append(ch if digits_left <= 4 else "*")
            digits_left -= 1
        else:
            masked.append(ch)
    return "".join(masked)


def mask_pii(text: str | None) -> str | None:
    """Mask SSNs (***-**-****) and valid card numbers (**** **** **** 1234)."""
    if not text:
        return text
    text = _SSN_RE.sub(SSN_TOKEN, text)
    text = _CARD_RE.sub(_mask_card_candidate, text)
    return text
