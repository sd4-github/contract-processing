from functools import wraps

import jwt
from flask import g, request

from . import core
jwks_client = jwt.PyJWKClient(core.KEYCLOAK_JWKS_URL)

def require(*required_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not core.AUTH_ENABLED:
                g.subject = "local-user"
                return view(*args, **kwargs)
            parts = request.headers.get("Authorization", "").split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return {"detail": "Use a Bearer access token."}, 401
            try:
                key = jwks_client.get_signing_key_from_jwt(parts[1]).key
                claims = jwt.decode(parts[1], key, algorithms=["RS256"], audience=core.KEYCLOAK_CLIENT_ID, issuer=core.KEYCLOAK_ISSUER)
            except jwt.PyJWTError: return {"detail": "Invalid or expired access token."}, 401
            roles = set(claims.get("realm_access", {}).get("roles", [])) | set(claims.get("resource_access", {}).get(core.KEYCLOAK_CLIENT_ID, {}).get("roles", []))
            if not roles.intersection(required_roles):
                return {"detail": "Insufficient role."}, 403
            g.subject = claims["sub"]
            return view(*args, **kwargs)
        return wrapped
    return decorator
