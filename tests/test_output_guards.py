from app.guardrails.output_guards import check_classification
from app.schemas import Classification

EMAIL = (
    "From: security@paypa1-support.com\nSubject: locked\n\n"
    "Verify at http://paypa1-secure-login.com/verify with your password."
)


def test_keeps_indicators_quoted_from_email():
    c = Classification(
        label="phishing",
        confidence=0.9,
        reason="credential harvesting",
        indicators=["http://paypa1-secure-login.com/verify", "your password"],
    )
    out = check_classification(c, email_text=EMAIL)
    assert out.classification.indicators == c.indicators
    assert out.trips == []


def test_drops_invented_indicators():
    c = Classification(
        label="phishing",
        confidence=0.9,
        reason="bad",
        indicators=["http://totally-made-up.example/pwn", "your password"],
    )
    out = check_classification(c, email_text=EMAIL)
    assert out.classification.indicators == ["your password"]
    assert any(t.code == "invented_indicator" for t in out.trips)


def test_scrubs_secret_in_reason():
    c = Classification(
        label="suspicious",
        confidence=0.5,
        reason="leaked key sk-abcdefghijklmnop12345 found",
        indicators=[],
    )
    out = check_classification(c, email_text=EMAIL)
    assert "sk-abcdefghijklmnop12345" not in out.classification.reason
    assert any(t.code == "secret_leak" for t in out.trips)
