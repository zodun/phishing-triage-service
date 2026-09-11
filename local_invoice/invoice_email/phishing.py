"""Conservative warning checks. No links are visited and no sender is certified."""

import ipaddress
import re
from email.utils import parseaddr
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field


class PhishingAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["suspicious", "no_obvious_signs", "unable_to_assess"]
    reasons: list[str] = Field(min_length=1, max_length=12)

    @property
    def label(self):
        return {
            "suspicious": "Suspicious — possible phishing",
            "no_obvious_signs": "No obvious warning signs",
            "unable_to_assess": "Be careful — check incomplete",
        }[self.status]

    @property
    def can_draft(self):
        return self.status == "no_obvious_signs"


class PhishingFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal[
        "credential_request",
        "payment_redirection",
        "deceptive_link",
        "supported_impersonation",
        "unsafe_attachment",
        "instruction_override",
    ]
    quote: str = Field(min_length=8, max_length=1000)
    explanation: str = Field(min_length=1, max_length=1000)


class ModelPhishingAssessment(PhishingAssessment):
    findings: list[PhishingFinding] = Field(default_factory=list, max_length=12)

    def grounded(self, sources):
        if self.status != "suspicious":
            return PhishingAssessment(status=self.status, reasons=self.reasons)
        if not self.findings or any(not any(f.quote in source for source in sources) for f in self.findings):
            return PhishingAssessment(
                status="unable_to_assess",
                reasons=[
                    "The AI returned a warning without matching source evidence. Recheck the message; this is not a phishing finding."
                ],
            )
        return PhishingAssessment(
            status="suspicious", reasons=[f"{f.explanation} Evidence: “{f.quote}”" for f in self.findings]
        )


def _domain(address):
    parsed = parseaddr(address)[1]
    return parsed.rsplit("@", 1)[-1].lower() if "@" in parsed else ""


def _host(url):
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def scan_message(message, pdf_text="", *, document_only=False):
    warnings = []
    context = []
    sender = _domain(message.sender)
    reply = _domain(message.reply_to)
    if reply and sender and reply != sender:
        context.append(
            "Context only: the reply-to domain differs from the sender. This can occur with legitimate email services."
        )
    if "SPAM" in message.labels:
        warnings.append("Gmail has placed this message in Spam.")
    if any(re.search(r"\.(exe|scr|bat|cmd|js|vbs|lnk|msi)$", name, re.I) for name in message.attachment_names):
        warnings.append("The email includes a file type that can run code, alongside its invoice attachment.")
    content = "\n".join((message.subject, message.body, message.html_text, pdf_text))
    content = re.sub("[\u200b-\u200d\ufeff]", "", content)
    if re.search(
        r"\b(enter|send|share|provide|confirm|verify|type)\b.{0,60}\b(password|verification code|one.time code|security code|login credentials|credit card number)\b",
        content,
        re.I,
    ):
        warnings.append("The message or PDF asks for a password, verification code, or other sensitive credentials.")
    if re.search(
        r"\b(new|updated|changed|different)\b.{0,35}\b(bank|payment|wire)\s+(account|details|instructions)\b|\b(bank|payment) details\b.{0,25}\bchanged\b",
        content,
        re.I,
    ):
        warnings.append(
            "The message or PDF mentions changed payment details. Confirm them through a contact you already know."
        )
    if re.search(
        r"\b(ignore|disregard)\b.{0,40}\b(previous|system|safety)\b.{0,30}\b(instructions|rules|checks)\b",
        content,
        re.I,
    ):
        warnings.append("The content attempts to override the app’s instructions or safety checks.")

    links = [(link.target, link.text) for link in message.links]
    links.extend((url.rstrip(".,);]"), "") for url in re.findall(r'https?://[^\s<>"\']+', content, re.I))
    for target, label in links:
        host = _host(target)
        shown = re.search(r"(?:https?://|www\.)[^\s<>]+", label, re.I)
        if shown:
            display_url = shown.group().rstrip(".,);]")
            display_host = _host(display_url if "://" in display_url else "https://" + display_url)
            if host and display_host and host != display_host:
                warnings.append("A link shows one website address but points to a different website.")
        try:
            parts = urlsplit(target)
            if parts.username or parts.scheme.lower() in ("javascript", "data", "file"):
                warnings.append("A link uses a misleading address or an unsafe link type.")
        except ValueError:
            warnings.append("A link contains an invalid address.")
        if "xn--" in host:
            context.append(
                "Context only: a link uses an internationalized domain; this alone does not establish impersonation."
            )
        try:
            ipaddress.ip_address(host)
            context.append("Context only: a link uses a numeric IP address; its destination has not been verified.")
        except ValueError:
            pass
        if host in {"bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "shorturl.at"}:
            context.append(
                "Context only: a shortened link hides its destination. Short links alone are not evidence of phishing."
            )
    warnings = list(dict.fromkeys(warnings))
    if warnings:
        return PhishingAssessment(status="suspicious", reasons=warnings[:12])
    if (not sender and not document_only) or not message.scan_complete:
        return PhishingAssessment(
            status="unable_to_assess",
            reasons=[
                "Sender information is missing or the email content is incomplete. The check cannot cover the whole message."
            ],
        )
    return PhishingAssessment(
        status="no_obvious_signs",
        reasons=[
            ("Document text checked; email sender and delivery headers were not provided." if document_only else "No strong warning signs were found by the automatic address, link, and text checks."),
            *list(dict.fromkeys(context)),
        ][:12],
    )


def combine_assessments(first, second):
    rank = {"no_obvious_signs": 0, "unable_to_assess": 1, "suspicious": 2}
    status = max((first.status, second.status), key=rank.get)
    # Do not mix a positive finding with reassuring text from another check.
    reasons = [reason for result in (first, second) if result.status == status for reason in result.reasons]
    return PhishingAssessment(status=status, reasons=list(dict.fromkeys(reasons))[:12])
