"""Static workspace presentation; never interpolate email/document content here."""

from pathlib import Path


def workspace_css():
    return Path(__file__).with_name("workspace.css").read_text()


HEADER = """<header class="app-header">
  <div class="app-brand"><span class="brand-mark" aria-hidden="true">↗</span>
    <span>Invoice<span class="brand-light">Email</span></span></div>
  <div class="header-caption">Less chasing. Better follow-ups.</div>
  <span class="local-badge">Local workspace</span>
</header>"""

SETUP_GUIDE = """<div class="setup-heading"><span>1</span><h2>Connect your Google account</h2></div>
<p class="setup-copy">Google requires a permission file before this app can read your email. Follow these steps once to get it.</p>
<ol class="setup-steps">
  <li><a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noopener noreferrer">Open Google Cloud ↗</a><br>Select or create a project and enable the Gmail API.</li>
  <li><a href="https://console.cloud.google.com/auth/audience" target="_blank" rel="noopener noreferrer">Set up your consent screen ↗</a><br>For a personal Gmail account, choose External and add your email as a test user.</li>
  <li><a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener noreferrer">Create an OAuth client ↗</a><br>Choose <strong>Desktop app</strong>, then download its JSON file.</li>
</ol>
<p class="setup-copy">Choose the downloaded file below and select <strong>Save Google file</strong>. We’ll show you the next step.</p>"""
