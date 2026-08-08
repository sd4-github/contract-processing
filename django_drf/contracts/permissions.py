from django.conf import settings
from rest_framework.permissions import BasePermission


class HasAnyRole(BasePermission):
    required_roles: set[str] = set()

    def has_permission(self, request, view):
        # No-auth mode exists only to make isolated API exploration possible without a running identity provider.
        if not settings.AUTH_ENABLED:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.roles.intersection(self.required_roles))


class CanSubmit(HasAnyRole):
    required_roles = {"submitter", "administrator"}


class CanView(HasAnyRole):
    required_roles = {"submitter", "reviewer", "administrator"}


class CanReview(HasAnyRole):
    required_roles = {"reviewer", "administrator"}
