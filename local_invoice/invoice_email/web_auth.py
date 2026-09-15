"""Browser-bound Google sign-in. Credentials stay in this server process."""
import os
import secrets
import time
from dataclasses import dataclass
from html import escape
from threading import RLock
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from .gmail import SCOPES

router = APIRouter()
COOKIE = 'phishguard_session'
TTL = 7 * 24 * 3600
_sessions = {}
_pending = {}
_lock = RLock()


@dataclass
class Session:
    credentials: object
    address: str
    expires: float
    csrf: str


def configured():
    uri = urlsplit(os.getenv('GOOGLE_REDIRECT_URI', ''))
    return bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET') and
                (uri.scheme == 'https' or (uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1'))))


def flow(**kwargs):
    return Flow.from_client_config({'web': {
        'client_id': os.environ['GOOGLE_CLIENT_ID'], 'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
    }}, scopes=SCOPES, redirect_uri=os.environ['GOOGLE_REDIRECT_URI'], **kwargs)


def session(request):
    cookies = request.cookies if request else {}
    with _lock:
        now = time.time()
        for key in list(_sessions):
            if _sessions[key].expires <= now:
                del _sessions[key]
        for key in list(_pending):
            if _pending[key][2] <= now:
                del _pending[key]
        return _sessions.get(cookies.get(COOKIE))


def mailbox(request):
    from google.auth.transport.requests import Request as GoogleRequest
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build
    import httplib2
    from .gmail import GmailMailbox
    current = session(request)
    if not current:
        raise ValueError('Your Gmail connection has expired. Reconnect Gmail to continue.')
    try:
        with _lock:
            if not current.credentials.valid:
                current.credentials.refresh(GoogleRequest())
        return GmailMailbox(build('gmail', 'v1', http=AuthorizedHttp(current.credentials, http=httplib2.Http(timeout=30)), cache_discovery=False))
    except Exception:
        with _lock:
            _sessions.pop(request.cookies.get(COOKIE), None)
        raise ValueError('Your Gmail connection has expired. Reconnect Gmail to continue.') from None


def cookie(response, name, value, age):
    response.set_cookie(name, value, max_age=age, httponly=True, samesite='lax', secure=os.getenv('GOOGLE_REDIRECT_URI', '').startswith('https://'), path='/')
    response.headers['Cache-Control'] = 'no-store'
    return response


def sign_in_error():
    return cookie(RedirectResponse('/invoices/', status_code=303), 'phishguard_auth_error', 'failed', 600)


@router.get('/auth/google')
def start(request: Request):
    if not configured():
        return RedirectResponse('/invoices/?signin=unconfigured', status_code=303)
    session(request)  # expire old entries
    oauth = flow(autogenerate_code_verifier=True)
    url, state = oauth.authorization_url(access_type='offline', prompt='select_account consent')
    binding = secrets.token_urlsafe(32)
    with _lock:
        if len(_pending) >= 1000:
            return RedirectResponse('/invoices/?signin=retry', status_code=303)
        _pending[state] = (binding, oauth, time.time() + 600)
    response = cookie(RedirectResponse(url, status_code=303), 'phishguard_login', binding, 600)
    response.delete_cookie('phishguard_auth_error', path='/')
    return response


@router.get('/auth/google/callback')
def callback(request: Request):
    state = request.query_params.get('state', '')
    with _lock:
        pending = _pending.get(state)
        valid = pending and pending[2] > time.time() and secrets.compare_digest(pending[0], request.cookies.get('phishguard_login', ''))
        if valid:
            _pending.pop(state)
    if not valid:
        return sign_in_error()
    try:
        if request.query_params.get('error') or not request.query_params.get('code'):
            raise ValueError('Sign-in declined')
        oauth = pending[1]
        oauth.fetch_token(code=request.query_params['code'])
        from googleapiclient.discovery import build
        address = build('gmail', 'v1', credentials=oauth.credentials, cache_discovery=False).users().getProfile(userId='me').execute()['emailAddress']
        sid = secrets.token_urlsafe(32)
        with _lock:
            _sessions.pop(request.cookies.get(COOKIE), None)
            _sessions[sid] = Session(oauth.credentials, address, time.time() + TTL, secrets.token_urlsafe(32))
        response = cookie(RedirectResponse('/invoices/', status_code=303), COOKIE, sid, TTL)
    except Exception:
        response = sign_in_error()
    response.delete_cookie('phishguard_login', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return response


@router.post('/auth/disconnect')
async def disconnect(request: Request):
    current = session(request)
    form = await request.form()
    if not current or not secrets.compare_digest(current.csrf, str(form.get('csrf', ''))):
        return sign_in_error()
    with _lock:
        _sessions.pop(request.cookies.get(COOKIE), None)
    response = RedirectResponse('/invoices/', status_code=303)
    response.delete_cookie(COOKIE, path='/')
    return response


GOOGLE_MARK = '<svg class="google-mark" aria-hidden="true" viewBox="0 0 24 24"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.8 3-4.3 3-7.3Z"/><path fill="#34A853" d="M12 22c2.7 0 5- .9 6.6-2.5L15.4 17c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.4 13.9A6 6 0 0 1 6.1 12c0-.7.1-1.3.3-1.9V7.5H3.1A10 10 0 0 0 2 12c0 1.6.4 3.2 1.1 4.5l3.3-2.6Z"/><path fill="#EA4335" d="M12 6c1.5 0 2.8.5 3.8 1.5l2.8-2.8A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.9 5.5l3.3 2.6A6 6 0 0 1 12 6Z"/></svg>'


def connection_html(request):
    current = session(request)
    if current:
        return (f'<div class="connected-account"><span class="account-dot" aria-hidden="true">✓</span><div><small>GMAIL CONNECTED</small><strong>{escape(current.address)}</strong></div>'
                f'<form action="/auth/disconnect" method="post"><input type="hidden" name="csrf" value="{current.csrf}"><button type="submit">Disconnect</button></form></div>')
    if not configured():
        return ('<button class="google-signin" disabled>' + GOOGLE_MARK + 'Continue with Google</button>'
                '<p class="permission-note">Read-only Gmail access</p>'
                '<aside class="installation-note"><strong>Google connection needs to be set up</strong>'
                '<span>The app owner needs to connect Google once. You can still upload a PDF.</span>'
                '<a href="/help">Connection setup ↗</a></aside>')
    expired = request and request.cookies.get(COOKIE)
    failed = request and request.cookies.get('phishguard_auth_error') == 'failed'
    note = '<p class="auth-error">Your Gmail connection has expired. Reconnect to continue.</p>' if expired else '<p class="auth-error">Could not connect to Google. Please try again.</p>' if failed else ''
    label = 'Reconnect Gmail' if expired else 'Continue with Google'
    return note + '<a class="google-signin" href="/auth/google">' + GOOGLE_MARK + label + '</a><p class="permission-note">Read-only Gmail access</p>'


@router.get('/help')
def developer_help():
    from starlette.responses import HTMLResponse
    from .appearance import workspace_css, HEADER

    hosted = bool(os.getenv("VERCEL"))
    callback = os.getenv("GOOGLE_REDIRECT_URI") or (
        "https://phishing-triage-service.vercel.app/auth/google/callback"
        if hosted else "http://127.0.0.1:8089/auth/google/callback"
    )
    configuration = (
        '<p>In Vercel, open Project Settings → Environment Variables. Add '
        'GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI. '
        'Add DEEPSEEK_API_KEY and set INVOICE_MODEL_PROVIDER to deepseek for invoice reading.</p>'
        '<p><a href="https://vercel.com/zoduns-projects/phishing-triage-service/settings/environment-variables" '
        'target="_blank" rel="noopener noreferrer">Open Vercel settings ↗</a></p>'
        if hosted else
        '<p>Copy .env.example to .env in the project root. Set GOOGLE_CLIENT_ID, '
        'GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, DEEPSEEK_API_KEY, and '
        'INVOICE_MODEL_PROVIDER=deepseek. Keep this file private.</p>'
    )
    restart = "Redeploy the project in Vercel after saving the variables." if hosted else "Restart python local_invoice/workspace_app.py."
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>PhishGuard — Connection setup</title><style>' + workspace_css() +
        '</style></head><body class="gradio-container">' + HEADER +
        '<main class="main help-page"><a href="/invoices/">← Back to invoice review</a>'
        '<section class="simple-intro"><h1>Connect Google</h1>'
        '<p>The app owner completes this setup once. Then you can sign in with Google.</p></section>'
        '<ol class="help-steps"><li><h2>Create a Google web client</h2>'
        '<p>Enable the Gmail API, configure the consent screen, add your account as a test user, '
        'and create an OAuth client of type Web application.</p></li>'
        '<li><h2>Register this redirect URL</h2><code>' + escape(callback) +
        '</code><p>Copy this exact URL into the Google client’s authorized redirect URIs.</p></li>'
        '<li><h2>Add the server credentials</h2>' + configuration + '</li>'
        '<li><h2>Apply the configuration</h2><p>' + restart + '</p></li></ol>'
        + ('<p>Cloud Gmail sessions still need shared storage before this deployment can reliably process inboxes across server restarts.</p>' if hosted else '') +
        '<p><a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener noreferrer">Open Google Cloud ↗</a></p>'
        '<a class="repository-link" href="https://github.com/zodun/phishing-triage-service" target="_blank" rel="noopener noreferrer">GitHub repository ↗</a>'
        '</main></body></html>'
    )
