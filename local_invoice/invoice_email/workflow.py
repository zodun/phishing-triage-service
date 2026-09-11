"""Process each PDF independently so one bad attachment does not hide others."""

from dataclasses import dataclass
from datetime import date

from .models import Invoice, Reminder, build_reminder
from .pdf import extract_pdf_text
from .phishing import PhishingAssessment, scan_message, combine_assessments


@dataclass
class Analysis:
    filename: str
    text: str = ""
    invoice: Invoice | None = None
    reminder: Reminder | None = None
    error: str = ""
    phishing: PhishingAssessment | None = None


def analyze_message(
    mailbox, message, extractor, *, today: date | None = None, signature="Accounts Receivable", document_only=False
) -> list[Analysis]:
    results = []
    email_check = scan_message(message, document_only=document_only)
    for attachment in message.attachments:
        result = Analysis(attachment.filename, phishing=email_check)
        try:
            if not email_check.can_draft:
                results.append(result)
                continue
            result.text = extract_pdf_text(mailbox.download_attachment(message.id, attachment))
            result.phishing = scan_message(message, result.text, document_only=document_only)
            if result.phishing.can_draft:
                try:
                    model_check = extractor.assess_phishing(result.text, message)
                    if not isinstance(model_check, PhishingAssessment):
                        raise ValueError("Invalid phishing result.")
                    result.phishing = combine_assessments(result.phishing, model_check)
                except Exception:
                    result.phishing = PhishingAssessment(
                        status="unable_to_assess",
                        reasons=["The AI phishing check could not finish. Try again before preparing a reminder."],
                    )
            if not result.phishing.can_draft:
                results.append(result)
                continue
            result.invoice = extractor.extract(result.text, message.body)
            result.reminder = build_reminder(result.invoice, source_text=result.text, today=today, signature=signature)
        except ValueError as exc:
            result.error = str(exc)
            result.phishing = PhishingAssessment(
                status="unable_to_assess",
                reasons=[
                    "The document could not be fully processed, so a complete phishing assessment is unavailable."
                ],
            )
        except Exception:
            # Provider errors can contain document text or credentials. Do not expose them in UI/logs.
            result.error = "Could not process this attachment. Check Gmail/model access and retry."
        results.append(result)
    return results
