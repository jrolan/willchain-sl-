from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsLawyerVerifier(BasePermission):
    """Grants view-level access to users with the LAWYER_VERIFIER role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.LAWYER_VERIFIER
        )


class IsCaseInitiator(BasePermission):
    """Object-level: grants access only to the user who created the case."""

    def has_object_permission(self, request, view, obj):
        return obj.initiator == request.user


class IsAssignedLawyer(BasePermission):
    """Object-level: grants access only to the lawyer assigned to the case."""

    def has_object_permission(self, request, view, obj):
        return obj.assigned_lawyer == request.user


class CanViewCase(BasePermission):
    """
    Object-level: case is visible to initiator, assigned lawyer, or administrator.
    Unrelated users receive no indication the case exists (IDOR prevention).
    """

    def has_object_permission(self, request, view, obj):
        u = request.user
        return (
            u == obj.initiator
            or u == obj.assigned_lawyer
            or u.role == User.Role.ADMINISTRATOR
        )

