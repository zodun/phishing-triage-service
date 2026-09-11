"""Static workspace presentation; never interpolate email/document content here."""

from pathlib import Path


def workspace_css():
    return Path(__file__).with_name("fonts.css").read_text() + Path(__file__).with_name("workspace.css").read_text()


HEADER = """<header class="app-header">
  <div class="app-brand"><svg class="brand-mark" width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true"><path d="m13 3 8 3v6c0 5-5 9-8 11-3-2-8-6-8-11V6l8-3Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="m9 12 3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <span>PhishGuard<small class="brand-caption">EMAIL &amp; INVOICE REVIEW</small></span></div>
  <p class="rail-description">Invoice review</p>
  <div class="rail-footer"><span class="local-badge"><i aria-hidden="true"></i> Local workspace</span><p>Gmail access is read-only.<br>You review every draft.</p></div>
</header>"""

SETUP_GUIDE = """<div class="setup-heading"><h2>Add your Google connection file</h2></div>
<p class="setup-copy">Already have the JSON file? Drop it below to continue.</p>
<details class="google-help"><summary>I don’t have this file — show me how</summary>
<p>This local app doesn’t have a shared Google sign-in client yet. Google requires you to register it once before connecting your inbox.</p>
<ol class="setup-steps">
<li><a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noopener noreferrer">Enable Gmail in Google Cloud ↗</a><br>Select or create a project, then choose Enable.</li>
<li><a href="https://console.cloud.google.com/auth/audience" target="_blank" rel="noopener noreferrer">Add your Gmail as a test user ↗</a><br>For a personal account, choose External.</li>
<li><a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener noreferrer">Create a Desktop app client ↗</a><br>Download its JSON file and drop it below.</li>
</ol></details>"""
