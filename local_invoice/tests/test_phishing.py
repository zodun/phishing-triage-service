import unittest
from unittest.mock import Mock
from datetime import date

from invoice_email.gmail import MailMessage, parse_message
from invoice_email.phishing import PhishingAssessment, scan_message, combine_assessments
from invoice_email.workflow import analyze_message
from invoice_email.ui import review_result, phishing_view
from test_invoice_email import encoded, make_pdf, TEXT, invoice


CLEAR = PhishingAssessment(status="no_obvious_signs", reasons=["No obvious warning signs in the supplied text."])


class PhishingTests(unittest.TestCase):
    def test_normal_forwarded_invoice_is_not_flagged_for_customer_sender_difference(self):
        message = MailMessage(
            "m1", sender="Forwarder <forwarder@example.com>", body="Please follow up on the attached invoice."
        )
        self.assertEqual(scan_message(message, TEXT).status, "no_obvious_signs")

    def test_credential_request_pauses_processing(self):
        risk = scan_message(
            MailMessage("m1", sender="someone@example.com", body="Enter your password to view the invoice.")
        )
        self.assertEqual(risk.status, "suspicious")
        self.assertTrue(any("password" in reason.lower() for reason in risk.reasons))

    def test_reply_address_mismatch_is_explained(self):
        raw = {
            "id": "m1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "billing@vendor.example"},
                    {"name": "Reply-To", "value": "collect@different.example"},
                ]
            },
        }
        risk = scan_message(parse_message(raw))
        self.assertEqual(risk.status, "no_obvious_signs")
        self.assertTrue(any("reply-to" in reason for reason in risk.reasons))

    def test_receipt_and_marketing_links_do_not_establish_phishing(self):
        from invoice_email.gmail import MailLink

        message = MailMessage(
            "receipt",
            sender="receipts@shop.example",
            body="Your Birkenstock purchase is confirmed. Thank you for shopping.",
            links=[MailLink("https://t.co/receipt", "View receipt")],
        )
        risk = scan_message(message, "Store location: Kingston. Ticket 123. Visa Card#: 2559. Paid.")
        self.assertEqual(risk.status, "no_obvious_signs")

    def test_model_warning_without_evidence_is_not_called_suspicious(self):
        import json
        from invoice_email.extraction import InvoiceExtractor

        client = Mock()
        client.chat.completions.create.return_value.choices = [
            Mock(
                message=Mock(
                    refusal=None,
                    content=json.dumps({"status": "suspicious", "reasons": ["A masked card number is suspicious."]}),
                )
            )
        ]
        risk = InvoiceExtractor(client, "test").assess_phishing(
            "Visa Card#: 2559", MailMessage("m", sender="receipt@shop.example")
        )
        self.assertEqual(risk.status, "unable_to_assess")

    def test_model_warning_requires_quote_from_input(self):
        import json
        from invoice_email.extraction import InvoiceExtractor

        for quote, expected in [
            ("Send your password", "suspicious"),
            ("Invented credential request", "unable_to_assess"),
        ]:
            with self.subTest(quote=quote):
                client = Mock()
                client.chat.completions.create.return_value.choices = [
                    Mock(
                        message=Mock(
                            refusal=None,
                            content=json.dumps(
                                {
                                    "status": "suspicious",
                                    "reasons": ["Credential theft request."],
                                    "findings": [
                                        {
                                            "category": "credential_request",
                                            "quote": quote,
                                            "explanation": "The message asks the recipient to disclose a password.",
                                        }
                                    ],
                                }
                            ),
                        )
                    )
                ]
                risk = InvoiceExtractor(client, "test").assess_phishing(
                    "", MailMessage("m", sender="billing@example.com", body="Send your password")
                )
                self.assertEqual(risk.status, expected)

    def test_html_link_is_checked_even_when_plain_text_alternative_exists(self):
        raw = {
            "id": "m1",
            "payload": {
                "headers": [{"name": "From", "value": "billing@example.com"}],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": encoded(b"Your invoice is attached.")}},
                    {
                        "mimeType": "text/html",
                        "body": {"data": encoded(b'<a href="https://steal.example/signin">https://vendor.example</a>')},
                    },
                ],
            },
        }
        message = parse_message(raw)
        self.assertEqual(message.links[0].target, "https://steal.example/signin")
        self.assertEqual(scan_message(message).status, "suspicious")

    def test_missing_sender_is_unable_to_assess(self):
        self.assertEqual(scan_message(MailMessage("m1", body="Invoice")).status, "unable_to_assess")

    def test_new_bank_details_inside_pdf_are_suspicious(self):
        message = MailMessage("m1", sender="billing@example.com")
        self.assertEqual(
            scan_message(message, "Our bank details have changed. Use our new bank account.").status, "suspicious"
        )

    def test_model_cannot_override_a_deterministic_warning(self):
        warning = PhishingAssessment(status="suspicious", reasons=["The reply address differs."])
        self.assertEqual(combine_assessments(warning, CLEAR).status, "suspicious")

    def test_email_warning_stops_attachment_download_and_draft(self):
        from invoice_email.gmail import Attachment

        message = MailMessage(
            "m1",
            sender="billing@example.com",
            body="Send your verification code.",
            attachments=[Attachment("invoice.pdf")],
        )
        mailbox, extractor = Mock(), Mock()
        results = analyze_message(mailbox, message, extractor)
        mailbox.download_attachment.assert_not_called()
        extractor.extract.assert_not_called()
        self.assertEqual(results[0].phishing.status, "suspicious")
        self.assertFalse(review_result("0", results)[7])

    def test_model_failure_blocks_reminder_with_explanation(self):
        from invoice_email.gmail import Attachment

        mailbox, extractor = Mock(), Mock()
        mailbox.download_attachment.return_value = make_pdf(TEXT)
        extractor.assess_phishing.side_effect = RuntimeError("private provider details")
        results = analyze_message(
            mailbox, MailMessage("m1", sender="billing@example.com", attachments=[Attachment("invoice.pdf")]), extractor
        )
        self.assertEqual(results[0].phishing.status, "unable_to_assess")
        extractor.extract.assert_not_called()
        self.assertNotIn("private provider", str(results[0]))

    def test_clear_message_can_still_generate_reminder(self):
        from invoice_email.gmail import Attachment

        mailbox, extractor = Mock(), Mock()
        mailbox.download_attachment.return_value = make_pdf(TEXT)
        extractor.assess_phishing.return_value = CLEAR
        extractor.extract.return_value = invoice()
        results = analyze_message(
            mailbox,
            MailMessage("m1", sender="billing@example.com", attachments=[Attachment("invoice.pdf")]),
            extractor,
            today=date(2026, 9, 9),
        )
        self.assertTrue(results[0].reminder.ready)
        self.assertEqual(results[0].phishing.status, "no_obvious_signs")

    def test_warning_html_is_escaped(self):
        from invoice_email.workflow import Analysis

        results = [
            Analysis(
                "invoice.pdf", phishing=PhishingAssessment(status="suspicious", reasons=["<script>alert(1)</script>"])
            )
        ]
        html = phishing_view("0", results)
        self.assertNotIn("<script>", html)
        self.assertIn("Suspicious", html)


if __name__ == "__main__":
    unittest.main()
