import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from .api import create_app


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "identity.db"
        self.client = TestClient(create_app(self.path))
        self.body = {"username": "astronaut.one", "password": "DemoPassword123!", "display_name": "Astronaut One", "mission": "Mars Demo"}

    def register_login(self, body=None):
        body = body or self.body
        registration = self.client.post('/api/v1/auth/register', json=body)
        self.assertEqual(registration.status_code, 201)
        login = self.client.post('/api/v1/auth/login', json={k: body[k] for k in ('username', 'password')})
        self.assertEqual(login.status_code, 200)
        return registration.json(), login.json()

    def test_registration_login_session_and_profile(self):
        profile, login = self.register_login()
        headers = {"Authorization": "Bearer " + login['access_token']}
        session = self.client.get('/api/v1/auth/session', headers=headers)
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()['astronaut_id'], profile['astronaut_id'])
        me = self.client.get('/api/v1/astronauts/me', headers=headers)
        self.assertEqual(me.json(), profile)
        self.assertEqual(me.headers['cache-control'], 'no-store')
        self.assertNotIn('password', json.dumps(me.json()))

    def test_storage_hashes_and_restart(self):
        profile, login = self.register_login()
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT password_hash, password_salt FROM astronauts').fetchone()
            session = db.execute('SELECT token_hash FROM sessions').fetchone()
        self.assertNotEqual(row[0], self.body['password'])
        self.assertNotEqual(session[0], login['access_token'])
        restarted = TestClient(create_app(self.path))
        response = restarted.get('/api/v1/astronauts/me', headers={'Authorization': 'Bearer '+login['access_token']})
        self.assertEqual(response.json()['astronaut_id'], profile['astronaut_id'])

    def test_duplicate_username_and_invalid_credentials(self):
        self.register_login()
        body = dict(self.body, username=self.body['username'].upper())
        self.assertEqual(self.client.post('/api/v1/auth/register', json=body).status_code, 409)
        for username in (self.body['username'], 'nonexistent'):
            response = self.client.post('/api/v1/auth/login', json={'username': username, 'password': 'WrongPassword!'})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['error']['code'], 'invalid_credentials')

    def test_missing_expired_and_revoked_sessions(self):
        self.assertEqual(self.client.get('/api/v1/astronauts/me').status_code, 401)
        _, login = self.register_login()
        headers = {'Authorization': 'Bearer '+login['access_token']}
        self.assertEqual(self.client.post('/api/v1/auth/logout', headers=headers).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/session', headers=headers).status_code, 401)
        login = self.client.post('/api/v1/auth/login', json={k:self.body[k] for k in ('username','password')}).json()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00Z'")
            db.commit()
        self.assertEqual(self.client.get('/api/v1/auth/session', headers={'Authorization':'Bearer '+login['access_token']}).status_code, 401)

    def test_profile_update_is_owned_and_id_is_immutable(self):
        first, login = self.register_login()
        second, _ = self.register_login(dict(self.body, username='astronaut.two'))
        headers = {'Authorization':'Bearer '+login['access_token']}
        changed = self.client.patch('/api/v1/astronauts/me', headers=headers, json={'display_name':'Updated', 'mission':None})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()['astronaut_id'], first['astronaut_id'])
        self.assertIsNone(changed.json()['mission'])
        self.assertEqual(self.client.patch('/api/v1/astronauts/me', headers=headers, json={'astronaut_id':second['astronaut_id']}).status_code, 422)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT display_name FROM astronauts WHERE astronaut_id=?',(second['astronaut_id'],)).fetchone()[0], self.body['display_name'])

    def test_invalid_payload_does_not_echo_password(self):
        response = self.client.post('/api/v1/auth/register', json=dict(self.body, password='secret'))
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('secret', response.text)
        self.assertEqual(self.client.post('/api/v1/auth/register', json=dict(self.body, display_name='   ')).status_code, 422)

    def test_local_cors_and_openapi(self):
        response = self.client.options('/api/v1/auth/login', headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'Content-Type'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
        spec = self.client.get('/openapi.json').json()
        self.assertTrue(spec['paths']['/api/v1/auth/session']['get']['security'])
        self.assertEqual(self.client.get('/health').json(), {'status':'ok'})


if __name__ == '__main__':
    unittest.main()
