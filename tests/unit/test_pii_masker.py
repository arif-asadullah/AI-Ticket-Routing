"""Unit tests for PII masking (test-plan P7).

SSNs and Luhn-valid card numbers must be redacted before storage; technical
numbers (ticket IDs, ports, IPs, timestamps) must pass through untouched.
"""
from backend.services.pii_masker import CARD_TOKEN, SSN_TOKEN, mask_pii


def test_ssn_is_masked():
    out = mask_pii("John Smith (SSN 123-45-6789) can't log in")
    assert "123-45-6789" not in out
    assert SSN_TOKEN in out


def test_valid_card_with_spaces_is_masked():
    out = mask_pii("card 4111 1111 1111 1111 was charged twice")
    assert "4111 1111 1111 1111" not in out
    assert CARD_TOKEN in out


def test_valid_card_with_dashes_is_masked():
    out = mask_pii("paid with 4111-1111-1111-1111 yesterday")
    assert CARD_TOKEN in out


def test_valid_card_without_separators_is_masked():
    out = mask_pii("card number 4111111111111111 on file")
    assert "4111111111111111" not in out
    assert CARD_TOKEN in out


def test_p7_ticket_fully_masked():
    # The exact adversarial input from test-plan P7
    out = mask_pii("John Smith (SSN 123-45-6789, card 4111 1111 1111 1111) can't log in from 10.0.1.55")
    assert "123-45-6789" not in out
    assert "4111" not in out
    assert "10.0.1.55" in out  # IPs are operational data, kept


def test_luhn_invalid_long_number_is_kept():
    # 16 digits but fails Luhn — a numeric ID, not a card
    out = mask_pii("trace id 1234 5678 9012 3456 in the logs")
    assert "1234 5678 9012 3456" in out


def test_technical_text_untouched():
    text = ("prod-db-01 refusing connections on port 5432 since 2026-06-12 10:43:28, "
            "PID 48151, error ERR-PG-001, ticket #448808")
    assert mask_pii(text) == text


def test_phone_like_numbers_kept():
    # Too short for the card pattern; phones are not masked by design
    text = "call me on 98765 43210 or extension 4521"
    assert mask_pii(text) == text


def test_none_and_empty_pass_through():
    assert mask_pii(None) is None
    assert mask_pii("") == ""
