import os
import time
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from invoice_email import web_auth as auth


class GoogleSignInTests(unittest.TestCase):
    def setUp(self):
        auth._sessions.clear()
        auth._pending.clear()
        app = FastAPI()
        app.include_router(auth.router)
        self.client = TestClient(app)
        self.config = patch.dict(os.environ, {'GOOGLE_CLIENT_ID':'test.apps.googleusercontent.com', 'GOOGLE_CLIENT_SECRET':'test-secret', 'GOOGLE_REDIRECT_URI':'http://127.0.0.1:8089/auth/google/callback'})
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_missing_configuration(self):
        with patch.dict(os.environ, {'GOOGLE_CLIENT_ID':''}):
            response = self.client.get('/auth/google', follow_redirects=False)
        self.assertIn('unconfigured', response.headers['location'])

    def test_callback_rejects_missing_or_wrong_state(self):
        response = self.client.get('/auth/google/callback?state=wrong&code=private', follow_redirects=False)
        self.assertIn('phishguard_auth_error=failed', response.headers['set-cookie'])
        self.assertEqual(auth._sessions, {})

    def start(self, oauth):
        oauth.authorization_url.return_value = ('https://accounts.google.com/o/oauth2/auth?state=test', 'test')
        with patch.object(auth, 'flow', return_value=oauth):
            response = self.client.get('/auth/google', follow_redirects=False)
        self.assertIn('HttpOnly', response.headers['set-cookie'])

    def test_success_rotates_session_and_disconnect_requires_csrf(self):
        oauth = Mock()
        self.start(oauth)
        with patch('googleapiclient.discovery.build') as build:
            build.return_value.users.return_value.getProfile.return_value.execute.return_value = {'emailAddress':'reader@example.test'}
            response = self.client.get('/auth/google/callback?state=test&code=private', follow_redirects=False)
        self.assertEqual(response.headers['location'], '/invoices/')
        sid = self.client.cookies.get(auth.COOKIE)
        self.assertEqual(auth._sessions[sid].address, 'reader@example.test')
        self.assertNotIn('private', response.text)
        self.client.post('/auth/disconnect', data={'csrf':'wrong'}, follow_redirects=False)
        self.assertIn(sid, auth._sessions)
        self.client.post('/auth/disconnect', data={'csrf':auth._sessions[sid].csrf}, follow_redirects=False)
        self.assertNotIn(sid, auth._sessions)
        self.assertNotIn('test', auth._pending)

    def test_another_browser_cannot_finish_login(self):
        oauth = Mock()
        self.start(oauth)
        self.client.cookies.clear()
        response = self.client.get('/auth/google/callback?state=test&code=private', follow_redirects=False)
        self.assertIn('phishguard_auth_error=failed', response.headers['set-cookie'])
        oauth.fetch_token.assert_not_called()

    def test_denied_and_expired_login(self):
        oauth = Mock()
        self.start(oauth)
        response = self.client.get('/auth/google/callback?state=test&error=access_denied', follow_redirects=False)
        self.assertIn('phishguard_auth_error=failed', response.headers['set-cookie'])
        oauth.fetch_token.assert_not_called()
        auth._sessions['expired'] = auth.Session(Mock(), 'a@example.test', time.time()-1, 'csrf')
        request = Mock(cookies={auth.COOKIE:'expired'})
        self.assertIsNone(auth.session(request))

    def test_refresh_uses_only_current_browser_credentials(self):
        credentials = Mock(valid=False)
        auth._sessions['mine'] = auth.Session(credentials, 'mine@example.test', time.time()+60, 'csrf')
        with patch('googleapiclient.discovery.build'), patch('google_auth_httplib2.AuthorizedHttp'):
            auth.mailbox(Mock(cookies={auth.COOKIE:'mine'}))
        credentials.refresh.assert_called_once()
        with self.assertRaisesRegex(ValueError, 'expired'):
            auth.mailbox(Mock(cookies={auth.COOKIE:'somebody-else'}))

    def test_refresh_failure_requires_reconnection(self):
        credentials = Mock(valid=False)
        credentials.refresh.side_effect = RuntimeError('private token')
        auth._sessions['mine'] = auth.Session(credentials, 'mine@example.test', time.time()+60, 'csrf')
        with self.assertRaisesRegex(ValueError, 'Reconnect Gmail'):
            auth.mailbox(Mock(cookies={auth.COOKIE:'mine'}))
        self.assertNotIn('mine', auth._sessions)
