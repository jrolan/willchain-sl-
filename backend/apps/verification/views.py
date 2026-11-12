"""
Views for Module 5: Verification & Legal Workflow.

All endpoints require IsAuthenticated and IsActiveAccount.
Follows the standard JSON response envelope:
  {'data': ...} / {'data': ..., 'message': ...} / {'error': {'code': ..., 'message': ...}}
"""

from django.http import FileResponse
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.models import Invitation
from apps.accounts.permissions import IsActiveAccount, IsAdministrator
from apps.accounts.services import log_audit_event
from apps.audit.models import AuditEvent
from apps.beneficiaries.models import BeneficiaryAllocation
from apps.documents.storage import private_document_storage

from .models import BeneficiaryNotificationOutbox, BeneficiaryRelease, CaseEvidence, VerificationCase
from .permissions import CanRetryReleaseNotification, CanViewCase, IsAssignedLawyer, IsAssignedLawyerForRelease, IsAssignedLawyerOrAdministrator, IsCaseInitiator, lawyer_case_scope_is_authorized
from .serializers import (
    CaseEvidenceSerializer,
    DecisionSerializer,
    BeneficiaryAllocationReviewSerializer,
    BeneficiaryReleaseAuthorizationSerializer,
    BeneficiaryReleaseStatusSerializer,
    LawyerBeneficiaryAllocationSerializer,
    EligibilityAssessmentInputSerializer,
    EligibilityAssessmentSerializer,
    EvidenceUploadSerializer,
    InformationRequestSerializer,
    InvitedLawyerAssignmentSerializer,
    LawyerAssignmentSerializer,
    Module8StatusSerializer,
    VerificationCaseCreateSerializer,
    VerificationCaseSerializer,
)
from .services import (
    assess_eligibility,
    assign_lawyer,
    assign_invited_lawyer,
    dispatch_beneficiary_notification,
    get_case_beneficiary_allocations,
    authorize_will_disclosure,
    begin_review,
    authorize_beneficiary_releases,
    create_case,
    record_decision,
    request_information,
    revoke_will_disclosure,
    review_beneficiary_allocation,
    set_evidence_sufficiency,
    submit_additional_information,
    submit_case,
    upload_evidence,
    withdraw_case,
)


class VerificationCaseListCreateAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]
    serializer_class = VerificationCaseSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.ADMINISTRATOR:
            return VerificationCase.objects.all().select_related('will', 'initiator', 'assigned_lawyer')
        else:
            return VerificationCase.objects.filter(
                Q(initiator=user) | Q(assigned_lawyer=user),
            ).select_related('will', 'initiator', 'assigned_lawyer').distinct()

    def get(self, request, *args, **kwargs):
        cases = self.get_queryset()
        serializer = self.get_serializer(cases, many=True)
        if request.user.role == User.Role.LAWYER_VERIFIER:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=request.user,
                details={'event': 'lawyer_assigned_case_list_accessed', 'case_count': len(serializer.data)},
            )
        return Response({'data': serializer.data})

    def post(self, request, *args, **kwargs):
        input_serializer = VerificationCaseCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        case = create_case(
            initiator=request.user,
            will=data.get('will'),
            case_type=data['case_type'],
            submission_type=data['submission_type'],
            claimed_executor_basis=data.get('claimed_executor_basis', ''),
            linked_prior_case=data.get('linked_prior_case'),
            request=request,
        )

        output_serializer = VerificationCaseSerializer(case)
        return Response(
            {'data': output_serializer.data, 'message': 'Verification case created successfully.'},
            status=status.HTTP_201_CREATED,
        )


class CaseBeneficiaryAllocationReviewAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyer]
    queryset = VerificationCase.objects.all()

    @transaction.atomic
    def post(self, request, pk, allocation_pk, *args, **kwargs):
        case = self.get_object()
        input_serializer = BeneficiaryAllocationReviewSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        allocation = get_object_or_404(
            BeneficiaryAllocation.objects.select_for_update().select_related('beneficiary'),
            pk=allocation_pk,
            beneficiary__will_id=case.will_id,
        )
        allocation = review_beneficiary_allocation(
            case,
            allocation,
            request.user,
            input_serializer.validated_data['review_status'],
            request=request,
        )
        return Response({
            'data': {
                'allocation_id': allocation.pk,
                'review_status': allocation.review_status,
                'reviewed_at': allocation.reviewed_at,
            },
            'message': 'Allocation review recorded.',
        })


class CaseBeneficiaryAllocationListAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyerOrAdministrator]
    queryset = VerificationCase.objects.all()

    def get(self, request, pk, *args, **kwargs):
        case = self.get_object()
        allocations = get_case_beneficiary_allocations(case, request.user)
        return Response({'data': LawyerBeneficiaryAllocationSerializer(allocations, many=True).data})


class CaseAuthorizeBeneficiaryReleaseAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyerForRelease]
    queryset = VerificationCase.objects.all()

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        case = get_object_or_404(VerificationCase.objects.select_for_update(), pk=pk)
        self.check_object_permissions(request, case)
        input_serializer = BeneficiaryReleaseAuthorizationSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        releases = authorize_beneficiary_releases(
            case,
            input_serializer.validated_data['allocation_ids'],
            request.user,
            request=request,
        )
        return Response({
            'data': {
                'releases': [
                    {'release_id': release.pk, 'allocation_id': release.allocation_id, 'status': release.status}
                    for release in releases
                ],
            },
            'message': 'Authorized allocation releases have been queued for notification.',
        })


class CaseBeneficiaryReleaseStatusAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, CanViewCase]
    queryset = VerificationCase.objects.all()

    def get(self, request, pk, *args, **kwargs):
        case = self.get_object()
        releases = BeneficiaryRelease.objects.filter(case=case)
        if request.user != case.assigned_lawyer and request.user.role != User.Role.ADMINISTRATOR:
            releases = releases.filter(
                allocation__beneficiary__beneficiary_user=request.user,
                allocation__beneficiary__normalized_email__iexact=request.user.email,
            )
        releases = releases.select_related('allocation').prefetch_related('notification')
        data = []
        for release in releases:
            notification = getattr(release, 'notification', None)
            data.append({
                'release_id': release.pk,
                'allocation_id': release.allocation_id,
                'allocation_type': release.allocation.allocation_type,
                'status': release.status,
                'notification_status': notification.status if notification else None,
                'authorized_at': release.authorized_at,
            })
        return Response({'data': BeneficiaryReleaseStatusSerializer(data, many=True).data})


class BeneficiaryReleaseNotificationRetryAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, CanRetryReleaseNotification]
    queryset = BeneficiaryRelease.objects.all()

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        release = get_object_or_404(BeneficiaryRelease.objects.select_for_update(), pk=pk)
        self.check_object_permissions(request, release)
        if release.status != BeneficiaryRelease.Status.AUTHORIZED:
            raise ValidationError('Only an active authorized release can be notified.')
        outbox, _ = BeneficiaryNotificationOutbox.objects.get_or_create(
            release=release,
            defaults={
                'recipient_email': release.allocation.beneficiary.normalized_email,
                'available_at': timezone.now(),
            },
        )
        outbox.status = BeneficiaryNotificationOutbox.Status.PENDING
        outbox.available_at = timezone.now()
        outbox.delivered_at = None
        outbox.last_error = ''
        outbox.save(update_fields=['status', 'available_at', 'delivered_at', 'last_error', 'updated_at'])
        release.access_token_hash = None
        release.token_expires_at = None
        release.save(update_fields=['access_token_hash', 'token_expires_at', 'updated_at'])
        log_audit_event(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            target_user=release.allocation.beneficiary.beneficiary_user,
            details={'event': 'beneficiary_notification_retry_requested', 'release_id': release.pk, 'outbox_id': outbox.pk},
        )
        transaction.on_commit(lambda: dispatch_beneficiary_notification(outbox.pk))
        return Response({'data': {'release_id': release.pk, 'notification_status': outbox.status}})


class VerificationCaseDetailAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, CanViewCase]
    serializer_class = VerificationCaseSerializer
    queryset = VerificationCase.objects.all().select_related('will', 'initiator', 'assigned_lawyer')

    def get(self, request, pk, *args, **kwargs):
        case = self.get_object()
        serializer = self.get_serializer(case)
        if request.user == case.assigned_lawyer:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=request.user,
                target_user=case.initiator,
                details={'event': 'lawyer_case_accessed', 'case_id': case.pk, 'case_type': case.case_type, 'status': case.status},
            )
        return Response({'data': serializer.data})


class CaseSubmitAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsCaseInitiator]
    serializer_class = VerificationCaseSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        case = submit_case(case, request.user, request=request)
        serializer = self.get_serializer(case)
        return Response({
            'data': serializer.data,
            'message': 'Verification case submitted for review.',
        })


class CaseAssignLawyerAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAdministrator]
    serializer_class = LawyerAssignmentSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            lawyer = User.objects.get(pk=input_serializer.validated_data['lawyer_id'])
        except User.DoesNotExist:
            raise NotFound({'lawyer_id': 'Lawyer user not found.'})

        case = assign_lawyer(case, lawyer, request.user, request=request)
        output_serializer = VerificationCaseSerializer(case)
        return Response({
            'data': output_serializer.data,
            'message': 'Lawyer verifier assigned successfully.',
        })


class CaseAssignInvitedLawyerAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsCaseInitiator]
    serializer_class = InvitedLawyerAssignmentSerializer
    queryset = VerificationCase.objects.all().select_related('will', 'initiator', 'assigned_lawyer')

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        case = get_object_or_404(VerificationCase.objects.select_for_update(), pk=pk)
        self.check_object_permissions(request, case)
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        invitation = get_object_or_404(
            Invitation.objects.select_for_update().select_related('accepted_user', 'will'),
            pk=input_serializer.validated_data['invitation_id'],
        )
        case = assign_invited_lawyer(case, invitation, request.user, request=request)
        return Response({
            'data': VerificationCaseSerializer(case).data,
            'message': 'The accepted legal verifier invitation was assigned to this case.',
        })


class CaseEligibilityAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyer]
    serializer_class = EligibilityAssessmentInputSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        assessment = assess_eligibility(
            case=case,
            lawyer=request.user,
            is_eligible=input_serializer.validated_data['is_eligible'],
            notes=input_serializer.validated_data.get('notes', ''),
            request=request,
        )
        return Response({
            'data': EligibilityAssessmentSerializer(assessment).data,
            'message': 'Eligibility assessment recorded.',
        })


class CaseEvidenceListCreateAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]
    parser_classes = [MultiPartParser, FormParser]

    def get_case(self):
        try:
            case = VerificationCase.objects.get(pk=self.kwargs['pk'])
        except VerificationCase.DoesNotExist:
            raise NotFound('Verification case not found.')
        self.check_object_permissions(self.request, case)
        if self.request.user == case.assigned_lawyer and not lawyer_case_scope_is_authorized(case, self.request.user):
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=self.request,
                actor=self.request.user,
                details={'event': 'case_evidence_access_denied', 'case_id': case.pk, 'operation': self.request.method},
            )
            raise PermissionDenied('This case is not currently authorized for lawyer evidence access.')
        return case

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsActiveAccount(), IsCaseInitiator()]
        return [IsAuthenticated(), IsActiveAccount(), CanViewCase()]

    def get(self, request, pk, *args, **kwargs):
        case = self.get_case()
        evidence_list = case.evidence.all()
        serializer = CaseEvidenceSerializer(evidence_list, many=True)
        if request.user == case.assigned_lawyer:
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=request.user,
                target_user=case.initiator,
                details={'event': 'lawyer_case_evidence_metadata_accessed', 'case_id': case.pk, 'evidence_count': len(serializer.data)},
            )
        return Response({'data': serializer.data})

    def post(self, request, pk, *args, **kwargs):
        case = self.get_case()
        input_serializer = EvidenceUploadSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        evidence = upload_evidence(
            case=case,
            actor=request.user,
            upload_file=input_serializer.validated_data['file'],
            evidence_type=input_serializer.validated_data['evidence_type'],
            description=input_serializer.validated_data.get('description', ''),
            request=request,
        )
        return Response(
            {
                'data': CaseEvidenceSerializer(evidence).data,
                'message': 'Evidence uploaded successfully.',
            },
            status=status.HTTP_201_CREATED,
        )


class CaseEvidenceDownloadAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request, pk, evidence_pk, *args, **kwargs):
        try:
            case = VerificationCase.objects.get(pk=pk)
        except VerificationCase.DoesNotExist:
            raise NotFound('Case not found.')

        u = request.user
        if not (u == case.initiator or u == case.assigned_lawyer or u.role == User.Role.ADMINISTRATOR):
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=u,
                details={'event': 'case_evidence_download_denied', 'case_id': case.pk, 'evidence_id': evidence_pk},
            )
            raise PermissionDenied('You do not have permission to download this evidence.')

        if u == case.assigned_lawyer and not lawyer_case_scope_is_authorized(case, u):
            log_audit_event(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=u,
                details={'event': 'case_evidence_download_denied', 'case_id': case.pk, 'evidence_id': evidence_pk},
            )
            raise PermissionDenied('This case is not currently authorized for lawyer evidence access.')

        try:
            evidence = CaseEvidence.objects.get(pk=evidence_pk, case=case)
        except CaseEvidence.DoesNotExist:
            raise NotFound('Evidence file not found.')

        source = private_document_storage.open(evidence.storage_key)
        log_audit_event(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=u,
            target_user=case.initiator,
            details={'event': 'case_evidence_downloaded', 'case_id': case.pk, 'evidence_id': evidence.pk},
        )
        response = FileResponse(source, content_type=evidence.media_type)
        response['Content-Disposition'] = f'attachment; filename="{evidence.original_filename}"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class CaseEvidenceSufficiencyAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request, pk, evidence_pk, *args, **kwargs):
        try:
            evidence = CaseEvidence.objects.get(pk=evidence_pk, case_id=pk)
        except CaseEvidence.DoesNotExist:
            raise NotFound('Evidence not found.')

        sufficiency_flag = request.data.get('sufficiency_flag', True)
        evidence = set_evidence_sufficiency(evidence, request.user, sufficiency_flag, request=request)
        return Response({
            'data': CaseEvidenceSerializer(evidence).data,
            'message': 'Evidence sufficiency updated.',
        })


class CaseBeginReviewAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyer]
    serializer_class = VerificationCaseSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        case = begin_review(case, request.user, request=request)
        return Response({
            'data': self.get_serializer(case).data,
            'message': 'Review started.',
        })


class CaseInformationRequestAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyer]
    serializer_class = InformationRequestSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        case = request_information(
            case=case,
            actor=request.user,
            notes=input_serializer.validated_data['notes'],
            request=request,
        )
        return Response({
            'data': VerificationCaseSerializer(case).data,
            'message': 'Information requested from claimant.',
        })


class CaseResubmitAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsCaseInitiator]
    serializer_class = VerificationCaseSerializer
    # select_related avoids an extra lazy lookup for eligibility_assessment when
    # submit_additional_information checks whether an assessment already exists.
    queryset = VerificationCase.objects.all().select_related('eligibility_assessment')

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        case = submit_additional_information(case, request.user, request=request)
        return Response({
            'data': self.get_serializer(case).data,
            'message': 'Additional information submitted.',
        })


class CaseDecisionAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsAssignedLawyer]
    serializer_class = DecisionSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        case = record_decision(
            case=case,
            actor=request.user,
            decision=input_serializer.validated_data['decision'],
            notes=input_serializer.validated_data.get('notes', ''),
            request=request,
        )
        return Response({
            'data': VerificationCaseSerializer(case).data,
            'message': f'Decision {case.status} recorded successfully.',
        })


class CaseWithdrawAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]
    serializer_class = VerificationCaseSerializer
    queryset = VerificationCase.objects.all()

    def post(self, request, pk, *args, **kwargs):
        case = self.get_object()
        case = withdraw_case(case, request.user, request=request)
        return Response({
            'data': self.get_serializer(case).data,
            'message': 'Case withdrawn.',
        })


class WillDisclosureAuthorizeAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk, *args, **kwargs):
        try:
            case = VerificationCase.objects.get(pk=pk)
        except VerificationCase.DoesNotExist:
            raise NotFound('Case not found.')

        upload_file = request.FILES.get('file')
        if not upload_file:
            raise ValidationError({'file': 'A will document file is required for disclosure.'})

        auth = authorize_will_disclosure(case, request.user, upload_file, request=request)
        return Response({
            'data': VerificationCaseSerializer(case).data,
            'message': 'Will disclosure authorized successfully.',
        })


class WillDisclosureRevokeAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request, pk, *args, **kwargs):
        try:
            case = VerificationCase.objects.get(pk=pk)
        except VerificationCase.DoesNotExist:
            raise NotFound('Case not found.')

        revoke_will_disclosure(case, request.user, request=request)
        return Response({'message': 'Will disclosure authorization revoked.'})


class WillDisclosureDownloadAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request, pk, *args, **kwargs):
        try:
            case = VerificationCase.objects.get(pk=pk)
        except VerificationCase.DoesNotExist:
            raise NotFound('Case not found.')

        if case.assigned_lawyer != request.user or not lawyer_case_scope_is_authorized(case, request.user):
            log_audit_event(
                AuditEvent.EventType.WILL_ACCESS_DENIED,
                request=request,
                actor=request.user,
                details={'will_id': case.will_id, 'case_id': case.pk, 'operation': 'DISCLOSURE_DOWNLOAD'},
            )
            raise PermissionDenied('This case is not currently authorized for lawyer document access.')

        auth = getattr(case, 'disclosure_authorization', None)
        if not auth or not auth.is_active:
            log_audit_event(
                AuditEvent.EventType.WILL_ACCESS_DENIED,
                request=request,
                actor=request.user,
                details={'will_id': case.will_id, 'case_id': case.pk, 'operation': 'DISCLOSURE_DOWNLOAD'},
            )
            raise PermissionDenied('No active disclosure authorization exists for this case.')

        source = private_document_storage.open(auth.storage_key)
        log_audit_event(
            AuditEvent.EventType.WILL_ACCESSED,
            request=request,
            actor=request.user,
            target_user=case.will.owner if case.will_id else None,
            details={'will_id': case.will_id, 'case_id': case.pk, 'access_scope': 'LAWYER_DISCLOSED_COPY_DOWNLOAD'},
        )
        response = FileResponse(source, content_type=auth.media_type)
        response['Content-Disposition'] = f'attachment; filename="{auth.original_filename}"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class Module8VerificationStatusAPIView(GenericAPIView):
    """
    Controlled status endpoint for Module 8.
    Excludes PRE_DEATH_REVIEW cases.
    Returns status for the latest POST_DEATH_VERIFY case for the will.

    Object-level authorization: only an administrator, the will owner, the case
    initiator, or the assigned lawyer may query this endpoint. Everyone else
    receives the same 404 as a nonexistent qualifying case so that verification
    outcomes cannot be enumerated across wills (anti-enumeration preserved).
    """
    permission_classes = [IsAuthenticated, IsActiveAccount]
    serializer_class = Module8StatusSerializer

    def get(self, request, will_pk, *args, **kwargs):
        case = (
            VerificationCase.objects.select_related('will')
            .filter(
                will_id=will_pk,
                case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
                status__in=[VerificationCase.Status.APPROVED, VerificationCase.Status.REJECTED],
            )
            .order_by('-updated_at')
            .first()
        )

        if not case:
            raise NotFound('No completed verification case found for this will.')

        # Object-level scoping: resolve the related will and case objects and
        # authorize against the actual related records, not a role name alone.
        will = case.will
        u = request.user
        is_authorised = (
            u.role == User.Role.ADMINISTRATOR
            or (will is not None and will.owner == u)
            or case.initiator == u
            or case.assigned_lawyer == u
        )
        if not is_authorised:
            # Same response as a nonexistent case to preserve anti-enumeration.
            raise NotFound('No completed verification case found for this will.')

        approved_row = case.status_history.filter(to_status=VerificationCase.Status.APPROVED).last()
        approved_at = approved_row.created_at if approved_row else None

        serializer = self.get_serializer({
            'case_id': case.pk,
            'will_id': will_pk,
            'case_type': case.case_type,
            'status': case.status,
            'approved_at': approved_at,
        })
        return Response({'data': serializer.data})
