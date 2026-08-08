from functools import cached_property

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions


class KeycloakUser:
    """Small authenticated principal built from a verified Keycloak access token."""

    def __init__(self, claims: dict):
        self.claims = claims
        self.id = claims["sub"]
        self.username = claims.get("preferred_username", claims["sub"])
        self.is_authenticated = True

    @cached_property
    def roles(self) -> set[str]:
        client_roles = self.claims.get("resource_access", {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get("roles", [])
        return set(self.claims.get("realm_access", {}).get("roles", [])) | set(client_roles)


class KeycloakJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        if not settings.AUTH_ENABLED:
            return None
        authorization = authentication.get_authorization_header(request).split()
        if not authorization:
            return None
        if len(authorization) != 2 or authorization[0].lower() != b"bearer":
            raise exceptions.AuthenticationFailed("Use a Bearer access token.")
        try:
            # The public issuer can differ from the container-network JWKS endpoint during local Compose use.
            signing_key = jwt.PyJWKClient(settings.KEYCLOAK_JWKS_URL).get_signing_key_from_jwt(authorization[1]).key
            claims = jwt.decode(authorization[1], signing_key, algorithms=["RS256"], audience=settings.KEYCLOAK_CLIENT_ID, issuer=settings.KEYCLOAK_ISSUER)
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed("Invalid or expired access token.") from exc
        return KeycloakUser(claims), claims
