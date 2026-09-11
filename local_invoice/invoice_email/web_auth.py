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


def connection_html(request):
    current = session(request)
    if current:
        return (f'<div class="connected-account"><strong>Connected to Gmail</strong><p>{escape(current.address)}</p>'
                f'<a href="/auth/google">Reconnect Gmail</a><form action="/auth/disconnect" method="post"><input type="hidden" name="csrf" value="{current.csrf}"><button type="submit">Disconnect</button></form></div>')
    if not configured():
        return '<p>Google sign-in has not been configured for this installation.</p>'
    if request and request.cookies.get(COOKIE):
        return '<p>Your Gmail connection has expired.</p><a class="google-signin" href="/auth/google">Reconnect Gmail</a>'
    failed = request and request.cookies.get('phishguard_auth_error') == 'failed'
    note = '<p>Google sign-in could not finish. Please try again.</p>' if failed else ''
    return note + '<a class="google-signin" href="/auth/google">Continue with Google</a><p>Read-only Gmail access.</p>'
