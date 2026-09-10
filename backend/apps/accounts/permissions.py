from rest_framework.permissions import BasePermission

from .models import User


class IsActiveAccount(BasePermission):
    message = 'Your account is not active.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.account_status == User.AccountStatus.ACTIVE
        )


class HasRole(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


def role_permission(*roles):
    return type('RolePermission', (HasRole,), {'allowed_roles': roles})
