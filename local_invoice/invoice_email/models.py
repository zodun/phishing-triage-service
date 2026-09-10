"""Invoice facts and deterministic reminder rules; no model or Gmail access."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from email import policy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_invoice: bool
    customer_name: str | None = None
    customer_email: str | None = None
    invoice_number: str | None = None
    issuer_name: str | None = None
    amount_due: str | None = None
    currency: str | None = None
    due_date: date | None = None
    payment_status: Literal["paid", "unpaid", "partial", "unknown"] = "unknown"
    evidence: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @field_validator("amount_due")
    @classmethod
    def valid_amount(cls, value):
        if value is None:
            return value
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Amount must be a decimal number.") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("Amount must be finite and non-negative.")
        return format(amount, "f")

    @field_validator("customer_name", "customer_email", "invoice_number", "issuer_name", "currency")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        if "\r" in value or "\n" in value or len(value) > 300:
            raise ValueError("Invoice field contains invalid text.")
        return value.strip() or None


@dataclass
class Reminder:
    ready: bool = False
    recipient: str = ""
    subject: str = ""
    body: str = ""
    status: str = "Needs review"
    warnings: list[str] = field(default_factory=list)


def _normalized(value):
    return " ".join(str(value).casefold().split())


def valid_email(value):
    return bool(re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", value or ""))


def _amount_in_quote(amount, quote):
    # Support decimal points and comma thousands separators without matching a
    # small amount inside a larger number. Other formats require manual review.
    numbers = re.findall(r"(?<![\w.,])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.,])", quote)
    return any(Decimal(number.replace(",", "")) == Decimal(amount) for number in numbers)


def _date_in_quote(expected, quote):
    for token in re.findall(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", quote):
        try:
            if datetime.strptime(token.replace("/", "-"), "%Y-%m-%d").date() == expected:
                return True
        except ValueError:
            pass
    for first, second, year in re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", quote):
        a, b = int(first), int(second)
        if a <= 12 and b <= 12 and a != b:
            continue  # A date such as 01/08 cannot establish August vs January.
        day, month = (a, b) if a > 12 else (b, a)
        try:
            if date(int(year), month, day) == expected:
                return True
        except ValueError:
            pass
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", quote, flags=re.IGNORECASE).replace(",", "")
    for pattern, formats in (
        (r"\b\d{1,2} [A-Za-z]+ \d{4}\b", ("%d %B %Y", "%d %b %Y")),
        (r"\b[A-Za-z]+ \d{1,2} \d{4}\b", ("%B %d %Y", "%b %d %Y")),
    ):
        for token in re.findall(pattern, cleaned):
            for fmt in formats:
                try:
                    if datetime.strptime(token, fmt).date() == expected:
                        return True
                except ValueError:
                    pass
    return False


def build_reminder(
    invoice: Invoice, *, source_text: str, today: date | None = None, signature: str = "Accounts Receivable"
) -> Reminder:
    today = today or date.today()
    if not invoice.is_invoice:
        return Reminder(status="Not an invoice", warnings=["This document was not identified as an invoice."])
    if invoice.payment_status == "paid" or (invoice.amount_due is not None and Decimal(invoice.amount_due) == 0):
        return Reminder(status="No balance to chase", warnings=["The document indicates payment or a zero balance."])
    missing = [
        name
        for name in ("customer_name", "invoice_number", "amount_due", "currency", "due_date")
        if getattr(invoice, name) is None
    ]
    if missing:
        return Reminder(warnings=["Missing invoice details: " + ", ".join(missing) + "."])
    if invoice.due_date >= today:
        return Reminder(status="Not overdue", warnings=["The invoice due date has not passed."])
    # Every essential fact must have a quote from the PDF, not the email body.
    source = _normalized(source_text)
    ungrounded = []
    for name in ("customer_name", "invoice_number", "amount_due", "currency", "due_date"):
        quote = _normalized(invoice.evidence.get(name, ""))
        if not quote or quote not in source:
            ungrounded.append(name)
        elif (
            name in ("customer_name", "invoice_number", "currency") and _normalized(getattr(invoice, name)) not in quote
        ):
            ungrounded.append(name)
        elif name == "amount_due" and not _amount_in_quote(invoice.amount_due, quote):
            ungrounded.append(name)
        elif name == "due_date" and not _date_in_quote(invoice.due_date, quote):
            ungrounded.append(name)
    if invoice.currency == "$":
        ungrounded.append("currency (ambiguous $ symbol)")
    if ungrounded:
        return Reminder(warnings=["Verify details without matching PDF evidence: " + ", ".join(ungrounded) + "."])

    warnings = ["Confirm the current balance against your payment records before using this reminder."]
    recipient = invoice.customer_email or ""
    email_quote = _normalized(invoice.evidence.get("customer_email", ""))
    if (
        not valid_email(recipient)
        or not email_quote
        or email_quote not in source
        or _normalized(recipient) not in email_quote
    ):
        recipient = ""
        warnings.append(
            "Customer email is missing or unverified. Enter the correct customer address after checking it."
        )
    amount = f"{invoice.currency} {invoice.amount_due}"
    subject = f"Payment reminder: invoice {invoice.invoice_number}"
    body = (
        f"Dear {invoice.customer_name},\n\n"
        f"I am following up on invoice {invoice.invoice_number}, which lists an outstanding "
        f"balance of {amount} and a due date of {invoice.due_date.isoformat()}. "
        "That due date has now passed.\n\n"
        "If this balance remains unpaid, please arrange payment and let us know the expected "
        "payment date. If you have already paid, thank you; please share the payment reference "
        "so we can reconcile our records.\n\n"
        "Please let us know if you need a copy of the invoice or have any questions.\n\n"
        f"Kind regards,\n{signature.strip() or 'Accounts Receivable'}"
    )
    return Reminder(True, recipient, subject, body, "Overdue — review payment status", warnings)


def export_email(recipient: str, subject: str, body: str) -> bytes:
    if not valid_email(recipient) or any(c in recipient + subject for c in "\r\n"):
        raise ValueError("Enter one valid customer email address and a single-line subject.")
    if not subject.strip() or not body.strip():
        raise ValueError("A subject and message are required.")
    message = EmailMessage(policy=policy.SMTP)
    message["To"] = recipient
    message["Subject"] = subject
    message["X-Unsent"] = "1"
    message.set_content(body)
    return message.as_bytes()
