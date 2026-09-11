"""Static workspace presentation; never interpolate email/document content here."""

from pathlib import Path


def workspace_css():
    return Path(__file__).with_name("fonts.css").read_text() + Path(__file__).with_name("workspace.css").read_text()


HEADER = """<header class="app-header">
  <div class="app-brand"><svg class="brand-mark" width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true"><path d="m13 3 8 3v6c0 5-5 9-8 11-3-2-8-6-8-11V6l8-3Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="m9 12 3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <span>PhishGuard</span></div>
  <p class="rail-description">Invoice review</p>
  <div class="rail-footer"><span class="local-badge"><i aria-hidden="true"></i> Local workspace</span><p>Gmail access is read-only.<br>You review every draft.</p></div>
</header>"""

SETUP_GUIDE = """<div class="setup-heading"><span>1</span><h2>Connect your Google account</h2></div>
<p class="setup-copy">Google requires a permission file before this app can read your email. Follow these steps once to get it.</p>
<ol class="setup-steps">
  <li><a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noopener noreferrer">Open Google Cloud ↗</a><br>Select or create a project and enable the Gmail API.</li>
  <li><a href="https://console.cloud.google.com/auth/audience" target="_blank" rel="noopener noreferrer">Set up your consent screen ↗</a><br>For a personal Gmail account, choose External and add your email as a test user.</li>
  <li><a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener noreferrer">Create an OAuth client ↗</a><br>Choose <strong>Desktop app</strong>, then download its JSON file.</li>
</ol>
<p class="setup-copy">Choose the downloaded file below and select <strong>Save Google file</strong>. We’ll show you the next step.</p>"""
