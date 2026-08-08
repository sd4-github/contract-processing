from drf_spectacular.extensions import OpenApiAuthenticationExtension


class KeycloakAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "contracts.authentication.KeycloakJWTAuthentication"
    name = "KeycloakBearer"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Keycloak OIDC access token.",
        }
