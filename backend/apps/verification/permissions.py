from rest_framework.permissions import BasePermission
from django.db.models import Q

from apps.audit.models import AuditEvent
from apps.accounts.services import log_audit_event
from apps.accounts.models import Invitation, User


def is_assigned_lawyer(case, user):
    if case.assigned_lawyer_id != user.pk or user.account_status != User.AccountStatus.ACTIVE:
        return False
    return user.role == User.Role.LAWYER_VERIFIER or Invitation.objects.filter(
        accepted_user=user,
        will_id=case.will_id,
        role=Invitation.RoleChoices.LAWYER_VERIFIER,
        status=Invitation.Status.ACCEPTED,
    ).exists()


def lawyer_case_scope_is_authorized(case, user):
    from .models import VerificationCase

    if (
        not is_assigned_lawyer(case, user)
        or case.status not in {
            VerificationCase.Status.OPEN,
            VerificationCase.Status.INFORMATION_REQUIRED,
            VerificationCase.Status.UNDER_REVIEW,
            VerificationCase.Status.APPROVED,
        }
    ):
        return False
    if case.case_type == VerificationCase.CaseType.PRE_DEATH_REVIEW:
        authorization = getattr(case, 'disclosure_authorization', None)
        return bool(authorization and authorization.is_active)
    return case.case_type == VerificationCase.CaseType.POST_DEATH_VERIFY


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
        allowed = (
            is_assigned_lawyer(obj, request.user)
        )
        if not allowed:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=request.user,
                details={'event': 'assigned_lawyer_action_denied', 'case_id': obj.pk, 'operation': request.method},
            )
        return allowed


class IsAssignedLawyerOrAdministrator(BasePermission):
    def has_object_permission(self, request, view, obj):
        return is_assigned_lawyer(obj, request.user) or request.user.role == User.Role.ADMINISTRATOR


class IsAssignedLawyerForRelease(BasePermission):
    def has_object_permission(self, request, view, obj):
        allowed = (
            is_assigned_lawyer(obj, request.user)
        )
        if not allowed:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=request.user,
                details={'event': 'beneficiary_release_action_denied', 'case_id': obj.pk, 'operation': request.method},
            )
        return allowed


class CanRetryReleaseNotification(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        allowed = (
            user.role == User.Role.ADMINISTRATOR
            or (
                is_assigned_lawyer(obj.case, user)
            )
        )
        if not allowed:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_notification_retry_denied', 'release_id': obj.pk},
            )
        return allowed


class CanViewCase(BasePermission):
    """
    Object-level: case is visible to initiator, assigned lawyer, or administrator.
    Unrelated users receive no indication the case exists (IDOR prevention).
    """

    def has_object_permission(self, request, view, obj):
        u = request.user
        allowed = (
            u == obj.initiator
            or is_assigned_lawyer(obj, u)
            or u.role == User.Role.ADMINISTRATOR
        )
        if not allowed:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=u,
                details={'event': 'verification_case_access_denied', 'case_id': obj.pk, 'operation': request.method},
            )
        return allowed


class IsAssignedLawyerOnAuthorizedCase(BasePermission):
    """Grant read-only access only when the lawyer is assigned to the relevant case."""

    def has_permission(self, request, view):
        if not (
            request.user
            and request.user.is_authenticated
            and request.user.account_status == User.AccountStatus.ACTIVE
        ):
            return False
        will_pk = view.kwargs.get('pk')
        if not will_pk:
            return False
        case_model = view.kwargs.get('case_model', None)
        if case_model is None:
            from .models import VerificationCase
            case_model = VerificationCase
        from .models import VerificationCase
        assigned_cases = case_model.objects.filter(
            will_id=will_pk,
            assigned_lawyer=request.user,
            status__in=[
                VerificationCase.Status.OPEN,
                VerificationCase.Status.UNDER_REVIEW,
                VerificationCase.Status.APPROVED,
                VerificationCase.Status.INFORMATION_REQUIRED,
            ],
        )
        if request.user.role != User.Role.LAWYER_VERIFIER:
            assigned_cases = assigned_cases.filter(
                # Scoped reviewer invitations grant case access without changing
                # the user's global account role.
                will__collaborator_invitations__accepted_user=request.user,
                will__collaborator_invitations__status=Invitation.Status.ACCEPTED,
                will__collaborator_invitations__role=Invitation.RoleChoices.LAWYER_VERIFIER,
            )
        has_authorized_case = assigned_cases.filter(
            Q(case_type=VerificationCase.CaseType.POST_DEATH_VERIFY)
            | Q(
                case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
                disclosure_authorization__is_active=True,
            )
        ).exists()
        if not has_authorized_case:
            log_audit_event(
                AuditEvent.EventType.WILL_ACCESS_DENIED,
                request=request,
                actor=request.user,
                details={'will_id': will_pk, 'operation': 'LAWYER_READ'},
            )
        return has_authorized_case
