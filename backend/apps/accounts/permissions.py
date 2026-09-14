from rest_framework.permissions import BasePermission, SAFE_METHODS

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
            and request.user.account_status == User.AccountStatus.ACTIVE
            and request.user.role in self.allowed_roles
        )


def role_permission(*roles):
    return type('RolePermission', (HasRole,), {'allowed_roles': roles})


class IsTestator(HasRole):
    allowed_roles = (User.Role.OWNER,)


class IsAdministrator(HasRole):
    allowed_roles = (User.Role.ADMINISTRATOR,)


class IsOwner(BasePermission):
    """
    Object-level permission to ensure a user can only access resources they own.
    Resolves ownership via direct user match, obj.owner, obj.user, or obj.inviter.
    """
    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if obj == request.user:
            return True

        for owner_field in ('owner', 'user', 'inviter', 'created_by'):
            if hasattr(obj, owner_field):
                return getattr(obj, owner_field) == request.user

        return False


class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission allowing read-only access for safe methods,
    while restricting write/mutation operations strictly to the resource owner.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        return IsOwner().has_object_permission(request, view, obj)


class BaseResourcePermission(BasePermission):
    """
    Foundational permission class for future modules (wills, documents, verifications).
    Enforces active account status at view-level and strict ownership/relationship at object-level.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.account_status == User.AccountStatus.ACTIVE
        )

    def has_object_permission(self, request, view, obj):
        return IsOwner().has_object_permission(request, view, obj)
