from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status

from . import core


@dataclass
class Principal:
    subject: str
    roles: set[str]


def current_principal(request: Request) -> Principal:
    if not core.AUTH_ENABLED:
        return Principal("local-user", {"submitter", "reviewer", "administrator"})
    authorization = request.headers.get("authorization", "").split()
    if len(authorization) != 2 or authorization[0].lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Use a Bearer access token.")
    try:
        key = jwt.PyJWKClient(core.KEYCLOAK_JWKS_URL).get_signing_key_from_jwt(authorization[1]).key
        claims = jwt.decode(authorization[1], key, algorithms=["RS256"], audience=core.KEYCLOAK_CLIENT_ID, issuer=core.KEYCLOAK_ISSUER)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired access token.") from exc
    roles = set(claims.get("realm_access", {}).get("roles", [])) | set(claims.get("resource_access", {}).get(core.KEYCLOAK_CLIENT_ID, {}).get("roles", []))
    return Principal(claims["sub"], roles)


def require(*roles: str):
    def check(principal: Principal = Depends(current_principal)):
        if not principal.roles.intersection(roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role.")
        return principal
    return check
