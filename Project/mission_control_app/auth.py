"""Resolve bearer identities through the local astronaut service."""
import httpx
from fastapi import HTTPException


def unauthorized():
    raise HTTPException(401, detail={"code": "unauthorized", "message": "A valid astronaut session is required."})


def unavailable():
    raise HTTPException(503, detail={"code": "identity_unavailable", "message": "Local astronaut authentication is unavailable. Retry shortly."})


class IdentityClient:
    def __init__(self, base_url, transport=None):
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def __call__(self, token):
        response = self._get("/api/v1/auth/session", token)
        try:
            identity = response.json()
            astronaut_id = identity.get("astronaut_id")
            if not isinstance(astronaut_id, str) or not astronaut_id:
                unavailable()
        except (ValueError, AttributeError):
            unavailable()
        return identity

    def profile(self, token):
        response = self._get("/api/v1/astronauts/me", token)
        try:
            profile = response.json()
            if not isinstance(profile.get("astronaut_id"), str) or not profile["astronaut_id"]:
                unavailable()
        except (ValueError, AttributeError):
            unavailable()
        return profile

    def _get(self, path, token):
        try:
            with httpx.Client(timeout=3, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                response = client.get(self.base_url + path, headers={"Authorization": "Bearer " + token})
        except httpx.HTTPError:
            unavailable()
        if response.status_code in (401, 403):
            unauthorized()
        if response.status_code != 200:
            unavailable()
        return response
