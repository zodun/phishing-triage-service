"""Local-only browser fixture: real PDF processing, substituted external services.

Run from the repository: PYTHONPATH=local_invoice:local_invoice/tests python
local_invoice/tests/workflow_fixture.py. Never use this entry point in production.
"""
import os
import time
from pathlib import Path
from unittest.mock import Mock

os.environ['LLM_FAKE'] = 'true'
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'false'

from test_invoice_email import TEXT, invoice, make_pdf
from invoice_email import ui, web_auth
from invoice_email.gmail import MailMessage, Attachment
from invoice_email.phishing import PhishingAssessment
from workspace_app import create_workspace

class FixtureExtractor:
    def assess_phishing(self, text, message):
        return PhishingAssessment(status='no_obvious_signs', reasons=['Test provider: no warning signs.'])

    def extract(self, text, body):
        assert 'Acme Ltd' in text, 'Actual PDF text must reach extraction'
        return invoice()

class FixtureMailbox:
    def search(self, query, limit):
        return [self.get_message('test-invoice')]

    def get_message(self, message_id):
        assert message_id == 'test-invoice'
        return MailMessage(id=message_id, sender='Accounts <accounts@acme.example>',
                           subject='Invoice INV-42', date='2026-08-01',
                           body='Please find the invoice attached.',
                           attachments=[Attachment(filename='invoice.pdf')])

    def download_attachment(self, message_id, attachment):
        return make_pdf(TEXT)

ui.setup_status = lambda: {'model_ready': True, 'gmail_ready': True, 'summary': 'Test fixture'}
ui.InvoiceExtractor.from_env = lambda: FixtureExtractor()
ui._web_mailbox = lambda request: FixtureMailbox()
web_auth._sessions['test-browser-session'] = web_auth.Session(Mock(), 'reader@example.test', time.time()+3600, 'test-csrf')
Path('/private/tmp/phishguard-test-invoice.pdf').write_bytes(make_pdf(TEXT))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_workspace(), host='127.0.0.1', port=8091, access_log=False)
