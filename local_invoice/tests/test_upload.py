import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from invoice_email.ui import _analyze_upload
from invoice_email.phishing import PhishingAssessment
from test_invoice_email import make_pdf, TEXT, invoice


class UploadTests(unittest.TestCase):
    def test_reads_pdf_without_gmail(self):
        extractor = Mock()
        extractor.assess_phishing.return_value = PhishingAssessment(status="no_obvious_signs", reasons=["Document checked"])
        extractor.extract.return_value = invoice()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invoice.pdf'
            path.write_bytes(make_pdf(TEXT))
            with patch('invoice_email.ui.setup_status', return_value={'model_ready': True}), patch('invoice_email.ui.InvoiceExtractor.from_env', return_value=extractor), patch('invoice_email.ui.connect_gmail') as gmail:
                result = _analyze_upload(str(path), 'Attached invoice', 'Accounts')
        gmail.assert_not_called()
        self.assertIn('Acme Ltd', result[1][0].text)
        self.assertEqual(extractor.extract.call_args.args[1], 'Attached invoice')
        self.assertTrue(result[-1])
        self.assertEqual(result[7], 'accounts@acme.example')
        self.assertIn('INV-42', result[9])

    def test_missing_file_clears_draft(self):
        result = _analyze_upload(None, '', '')
        self.assertEqual(result[1], [])
        self.assertIn('Choose a PDF', result[3])
        self.assertFalse(result[-1])

    def test_corrupt_pdf_blocks_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'broken.pdf'
            path.write_bytes(b'not a PDF')
            with patch('invoice_email.ui.setup_status', return_value={'model_ready': True}), patch('invoice_email.ui.InvoiceExtractor.from_env') as factory:
                result = _analyze_upload(str(path), '', '')
        factory.return_value.extract.assert_not_called()
        self.assertFalse(result[-1])
        self.assertTrue(result[1][0].error)
