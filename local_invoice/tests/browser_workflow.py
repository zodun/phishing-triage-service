"""Run against workflow_fixture.py; external services are test substitutes."""
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.webkit.launch()
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    page.goto('http://127.0.0.1:8091/invoices/', wait_until='domcontentloaded')
    page.get_by_text('Or upload a PDF invoice', exact=True).click()
    page.locator('#direct-upload input[type=file]').set_input_files('/private/tmp/phishguard-test-invoice.pdf')
    page.get_by_role('button', name='Read PDF & prepare reminder', exact=True).click()
    expect(page.locator('#draft-recipient textarea')).to_have_value('accounts@acme.example', timeout=30000)
    expect(page.locator('#invoice-summary')).to_contain_text('INV-42')
    expect(page.locator('#draft-message textarea')).to_have_value(re.compile('Acme Ltd'))
    page.locator('#draft-subject textarea').fill('Reviewed invoice reminder')
    page.get_by_role('button', name='Download email draft', exact=True).click()
    link = page.locator('#draft-download a[download]')
    expect(link).to_be_visible(timeout=15000)
    page.locator('#draft-subject textarea').fill('Regenerated invoice reminder')
    expect(link).not_to_be_visible()
    page.get_by_role('button', name='Download email draft', exact=True).click()
    expect(link).to_be_visible(timeout=15000)
    with page.expect_download() as event:
        link.click()
    download = event.value
    content = Path(download.path()).read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(content)
    assert message['To'] == 'accounts@acme.example'
    assert message['Subject'] == 'Regenerated invoice reminder'
    assert '125.50' in message.get_body().get_content()
    page.locator('#draft-subject textarea').fill('Edited after download')
    expect(link).not_to_be_visible()
    print('PASS: real PDF upload → extracted text → reminder → edited .eml download → stale download cleared')
    context.close()
    context = browser.new_context()
    context.add_cookies([{'name':'phishguard_session','value':'test-browser-session','url':'http://127.0.0.1:8091'}])
    page = context.new_page()
    page.goto('http://127.0.0.1:8091/invoices/', wait_until='domcontentloaded')
    page.get_by_role('button', name='Search invoices', exact=True).click()
    page.get_by_role('radio').first.check()
    page.get_by_role('button', name='Check selected email', exact=True).click()
    expect(page.locator('#draft-recipient textarea')).to_have_value('accounts@acme.example', timeout=30000)
    expect(page.locator('#invoice-summary')).to_contain_text('INV-42')
    print('PASS: test Gmail session → search → select email → actual attachment text → reminder')
    context.close()
    browser.close()
