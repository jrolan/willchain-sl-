from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.accounts.permissions import CanManageOwnWills, IsActiveAccount, IsOwner
from apps.accounts.serializers import RegistrationSerializer, UserSerializer
from apps.accounts.services import send_email_verification
from apps.audit.models import AuditEvent
from apps.verification.models import BeneficiaryRelease, VerificationCase
from apps.wills.models import Will
from .models import BeneficiaryAllocation, BeneficiaryInvitation, WillBeneficiary
from .services import generate_identity_verification_code, record_beneficiary_audit, send_identity_verification_code
from .serializers import (
    AcceptInvitationSerializer,
    BeneficiaryAllocationAccessSerializer,
    BeneficiaryAllocationSerializer,
    BeneficiaryInvitationSerializer,
    BeneficiaryInvitationPreviewSerializer,
    BeneficiaryReleaseIdentityVerifySerializer,
    BeneficiaryReleaseRegistrationSerializer,
    BeneficiaryReleaseTokenSerializer,
    CreateWillBeneficiarySerializer,
    BeneficiarySelfRelationshipSerializer,
    WillBeneficiarySerializer,
)


def get_valid_beneficiary_release(raw_token, lock=False):
    if not isinstance(raw_token, str) or not raw_token:
        return None
    queryset = BeneficiaryRelease.objects
    if lock:
        queryset = queryset.select_for_update()
    return queryset.select_related('allocation__beneficiary', 'case').filter(
        access_token_hash=BeneficiaryRelease.hash_access_token(raw_token),
        status__in=[BeneficiaryRelease.Status.AUTHORIZED, BeneficiaryRelease.Status.ACKNOWLEDGED],
        token_expires_at__gt=timezone.now(),
        case__case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
        case__status=VerificationCase.Status.APPROVED,
        allocation__review_status=BeneficiaryAllocation.ReviewStatus.VERIFIED,
        allocation__reviewed_case=F('case'),
    ).first()


def mask_email(email):
    local, separator, domain = email.partition('@')
    return f'{local[:1]}***@{domain}' if separator else '***'


def relationship_has_authorized_release(relationship):
    return relationship.allocations.filter(
        review_status=BeneficiaryAllocation.ReviewStatus.VERIFIED,
        release_authorization__status__in=[
            BeneficiaryRelease.Status.AUTHORIZED,
            BeneficiaryRelease.Status.ACKNOWLEDGED,
        ],
        release_authorization__case__case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
        release_authorization__case__status=VerificationCase.Status.APPROVED,
    ).exists()


class WillBeneficiaryListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = WillBeneficiarySerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills)

    def get_queryset(self):
        return WillBeneficiary.objects.filter(will__owner=self.request.user, will_id=self.kwargs['will_id']).select_related('will', 'beneficiary_user').prefetch_related('invitations')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        will = get_object_or_404(
            Will.objects.select_for_update(),
            owner=request.user,
            pk=self.kwargs['will_id'],
        )
        if will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Only DRAFT wills can manage beneficiaries.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CreateWillBeneficiarySerializer(data=request.data, context={'request': request, 'will_id': will.pk})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                relationship = serializer.save()
        except IntegrityError:
            return Response(
                {'error': {'code': 'BENEFICIARY_CONFLICT', 'message': 'A matching beneficiary relationship already exists for this will.'}},
                status=status.HTTP_409_CONFLICT,
            )
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_created', 'will_id': will.pk, 'beneficiary_id': relationship.pk},
        )
        response = Response({'data': WillBeneficiarySerializer(relationship).data, 'message': 'Beneficiary added. No notification is sent before authorized release.'}, status=status.HTTP_201_CREATED)
        return response

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {'data': response.data}
        return response


class WillBeneficiaryDetailAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = WillBeneficiarySerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills, IsOwner)

    def get_queryset(self):
        return WillBeneficiary.objects.filter(will__owner=self.request.user).select_related('will', 'beneficiary_user').prefetch_related('invitations')

    def get_object(self):
        obj = get_object_or_404(WillBeneficiary, will__owner=self.request.user, pk=self.kwargs['pk'], will_id=self.kwargs['will_id'])
        self.check_object_permissions(self.request, obj)
        return obj

    def get_locked_object(self, request):
        will = get_object_or_404(
            Will.objects.select_for_update(),
            owner=request.user,
            pk=self.kwargs['will_id'],
        )
        obj = get_object_or_404(
            WillBeneficiary.objects.select_for_update(),
            will=will,
            pk=self.kwargs['pk'],
        )
        self.check_object_permissions(request, obj)
        return obj

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        obj = self.get_locked_object(request)
        if obj.will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Only DRAFT wills can update beneficiary relationships.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if obj.status not in (WillBeneficiary.Status.PENDING, WillBeneficiary.Status.ACTIVE):
            return Response(
                {'error': {'code': 'RELATIONSHIP_NOT_EDITABLE', 'message': 'Only pending or active beneficiary relationships can be updated.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'status' in request.data:
            return Response(
                {'error': {'code': 'STATUS_FORBIDDEN', 'message': 'Status updates are server-controlled for beneficiary records.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = super().update(request, *args, **kwargs)
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_updated', 'relationship_id': obj.pk, 'will_id': obj.will_id, 'updated_fields': sorted(request.data.keys())},
        )
        response.data = {'data': response.data, 'message': 'Beneficiary updated successfully.'}
        return response

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        obj = self.get_locked_object(request)
        if obj.will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Only DRAFT wills can revoke beneficiary relationships.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if obj.status not in (WillBeneficiary.Status.PENDING, WillBeneficiary.Status.ACTIVE):
            return Response(
                {'error': {'code': 'RELATIONSHIP_NOT_REVOCABLE', 'message': 'Only pending or active beneficiary relationships can be revoked.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.revoke()
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_revoked', 'relationship_id': obj.pk, 'will_id': obj.will_id},
        )
        return Response({'data': {'id': obj.pk, 'status': obj.status}, 'message': 'Beneficiary revoked successfully.'})


class WillBeneficiaryAllocationListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = BeneficiaryAllocationSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills)

    def get_queryset(self):
        return BeneficiaryAllocation.objects.filter(
            beneficiary__will__owner=self.request.user,
            beneficiary__will_id=self.kwargs['will_id'],
            beneficiary_id=self.kwargs['beneficiary_id'],
        ).select_related('beneficiary', 'beneficiary__will')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        will = get_object_or_404(
            Will.objects.select_for_update(),
            pk=self.kwargs['will_id'],
            owner=request.user,
        )
        if will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Allocations can only be changed while the will is a draft.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        beneficiary = get_object_or_404(
            WillBeneficiary.objects.select_for_update(),
            pk=self.kwargs['beneficiary_id'],
            will=will,
            relationship_type__in=[
                WillBeneficiary.RelationshipType.PRIMARY,
                WillBeneficiary.RelationshipType.CONTINGENT,
                WillBeneficiary.RelationshipType.RESIDUAL,
            ],
            status__in=[WillBeneficiary.Status.PENDING, WillBeneficiary.Status.ACTIVE],
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocation = serializer.save(beneficiary=beneficiary)
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_allocation_created', 'will_id': will.pk, 'relationship_id': beneficiary.pk, 'allocation_id': allocation.pk},
        )
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {'data': response.data}
        return response


class WillBeneficiaryAllocationDetailAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = BeneficiaryAllocationSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills)

    def get_queryset(self):
        return BeneficiaryAllocation.objects.filter(
            beneficiary__will__owner=self.request.user,
            beneficiary__will_id=self.kwargs['will_id'],
            beneficiary_id=self.kwargs['beneficiary_id'],
        ).select_related('beneficiary', 'beneficiary__will')

    def get_object(self):
        allocation = get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, allocation)
        return allocation

    def ensure_draft(self, allocation):
        if allocation.beneficiary.will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Allocations can only be changed while the will is a draft.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        allocation = self.get_object()
        draft_error = self.ensure_draft(allocation)
        if draft_error:
            return draft_error
        if any(field in request.data for field in ('review_status', 'reviewed_by', 'reviewed_at', 'beneficiary')):
            return Response(
                {'error': {'code': 'ALLOCATION_REVIEW_FIELDS_FORBIDDEN', 'message': 'Allocation review fields are controlled by the verification workflow.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = super().update(request, *args, **kwargs)
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_allocation_updated', 'will_id': allocation.beneficiary.will_id, 'relationship_id': allocation.beneficiary_id, 'allocation_id': allocation.pk},
        )
        response.data = {'data': response.data}
        return response

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        allocation = self.get_object()
        draft_error = self.ensure_draft(allocation)
        if draft_error:
            return draft_error
        allocation_id = allocation.pk
        relationship_id = allocation.beneficiary_id
        will_id = allocation.beneficiary.will_id
        allocation.delete()
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_allocation_deleted', 'will_id': will_id, 'relationship_id': relationship_id, 'allocation_id': allocation_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BeneficiaryInvitationResendAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills, IsOwner)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'beneficiary_invitation_resend'

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        will = get_object_or_404(
            Will.objects.select_for_update(),
            owner=request.user,
            pk=self.kwargs['will_id'],
        )
        relationship = get_object_or_404(
            WillBeneficiary.objects.select_for_update(),
            will=will,
            pk=self.kwargs['pk'],
        )
        self.check_object_permissions(request, relationship)
        if relationship.will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Only DRAFT wills can resend beneficiary invitations.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if relationship.status != WillBeneficiary.Status.PENDING:
            return Response(
                {'error': {'code': 'RELATIONSHIP_NOT_PENDING', 'message': 'Only pending beneficiary relationships can be reinvited.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'error': {'code': 'RELEASE_NOT_AUTHORIZED', 'message': 'Beneficiary invitations are sent only after an allocation is authorized for release.'}},
            status=status.HTTP_403_FORBIDDEN,
        )


class BeneficiaryInvitationRegistrationAPIView(generics.GenericAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'auth'

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        raw_token = request.data.get('invitation_token')
        email = request.data.get('email')
        if not isinstance(raw_token, str) or not raw_token or not isinstance(email, str):
            return Response(
                {'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation or registration details are invalid.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invitation_data = BeneficiaryInvitation.objects.filter(
            token_hash=BeneficiaryInvitation.hash_token(raw_token),
        ).values('id', 'relationship_id', 'relationship__will_id').first()
        if not invitation_data:
            return Response(
                {'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation or registration details are invalid.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        will = Will.objects.select_for_update().filter(pk=invitation_data['relationship__will_id']).first()
        relationship = WillBeneficiary.objects.select_for_update().filter(
            pk=invitation_data['relationship_id'], will=will,
        ).first() if will else None
        invitation = BeneficiaryInvitation.objects.select_for_update().filter(
            pk=invitation_data['id'], relationship=relationship,
        ).first() if relationship else None
        if (
            not invitation
            or not invitation.is_valid()
            or invitation.relationship.status != WillBeneficiary.Status.PENDING
            or invitation.relationship.will.status != Will.Status.DRAFT
            or invitation.recipient_email.lower() != email.strip().lower()
            or not relationship_has_authorized_release(invitation.relationship)
        ):
            return Response(
                {'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation or registration details are invalid.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        registration_data = request.data.copy()
        registration_data.pop('invitation_token', None)
        serializer = self.get_serializer(
            data=registration_data,
            context={'registration_role': User.Role.MEMBER},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_beneficiary_audit(
            AuditEvent.EventType.USER_REGISTERED,
            request=request,
            target_user=user,
            details={'role': user.role, 'registration_source': 'beneficiary_invitation'},
        )
        send_email_verification(user)
        return Response(
            {
                'data': UserSerializer(user).data,
                'message': 'Account created. Verify your email, then return to the invitation to accept it.',
            },
            status=status.HTTP_201_CREATED,
        )


class BeneficiaryInvitationPreviewAPIView(generics.RetrieveAPIView):
    serializer_class = BeneficiaryInvitationPreviewSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount)

    def get_object(self):
        token = self.kwargs['token']
        token_hash = BeneficiaryInvitation.hash_token(token)
        queryset = BeneficiaryInvitation.objects.select_related('relationship__will').filter(
            token_hash=token_hash,
            recipient_email__iexact=self.request.user.email,
            status=BeneficiaryInvitation.Status.PENDING,
            expires_at__gt=timezone.now(),
            relationship__status=WillBeneficiary.Status.PENDING,
            relationship__will__status=Will.Status.DRAFT,
            relationship__allocations__review_status=BeneficiaryAllocation.ReviewStatus.VERIFIED,
            relationship__allocations__release_authorization__status=BeneficiaryRelease.Status.AUTHORIZED,
            relationship__allocations__release_authorization__case__case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            relationship__allocations__release_authorization__case__status=VerificationCase.Status.APPROVED,
        )
        return get_object_or_404(queryset.distinct())


class BeneficiaryInvitationAcceptAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)
    serializer_class = AcceptInvitationSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = AcceptInvitationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        validated_invitation = serializer.validated_data['invitation']
        will = Will.objects.select_for_update().get(pk=validated_invitation.relationship.will_id)
        relationship = WillBeneficiary.objects.select_for_update().get(
            pk=validated_invitation.relationship_id,
            will=will,
        )
        invitation = BeneficiaryInvitation.objects.select_for_update().get(
            pk=validated_invitation.pk,
            relationship=relationship,
        )
        if (
            not invitation.is_valid()
            or relationship.status != WillBeneficiary.Status.PENDING
            or will.status != Will.Status.DRAFT
            or invitation.recipient_email.lower() != user.email.lower()
            or not user.email_verified
            or user.account_status != User.AccountStatus.ACTIVE
            or not relationship_has_authorized_release(relationship)
        ):
            return Response(
                {'error': {'code': 'INVALID_INVITATION', 'message': 'Invitation is invalid, expired, or no longer available.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relationship.beneficiary_user = user
        relationship.status = WillBeneficiary.Status.ACTIVE
        relationship.accepted_at = timezone.now()
        relationship.save(update_fields=['beneficiary_user', 'status', 'accepted_at', 'updated_at'])

        invitation.status = BeneficiaryInvitation.Status.ACCEPTED
        invitation.token_hash = None
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'token_hash', 'responded_at', 'updated_at'])

        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=user,
            details={'event': 'beneficiary_invitation_accepted', 'relationship_id': relationship.pk, 'will_id': relationship.will_id},
        )

        return Response({'data': BeneficiarySelfRelationshipSerializer(relationship).data, 'message': 'Invitation accepted successfully.'})


class BeneficiaryInvitationDeclineAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        if not isinstance(token, str) or not token:
            return Response({'error': {'code': 'TOKEN_REQUIRED', 'message': 'Invitation token is required.'}}, status=status.HTTP_400_BAD_REQUEST)
        invitation_data = BeneficiaryInvitation.objects.filter(
            token_hash=BeneficiaryInvitation.hash_token(token),
        ).values('id', 'relationship_id', 'relationship__will_id').first()
        if not invitation_data:
            return Response({'error': {'code': 'INVALID_TOKEN', 'message': 'Invitation is invalid or expired.'}}, status=status.HTTP_400_BAD_REQUEST)
        will = Will.objects.select_for_update().filter(pk=invitation_data['relationship__will_id']).first()
        relationship = WillBeneficiary.objects.select_for_update().filter(
            pk=invitation_data['relationship_id'], will=will,
        ).first() if will else None
        invitation = BeneficiaryInvitation.objects.select_for_update().filter(
            pk=invitation_data['id'], relationship=relationship,
        ).first() if relationship else None
        if (
            not invitation
            or not invitation.is_valid()
            or relationship.status != WillBeneficiary.Status.PENDING
            or not relationship_has_authorized_release(relationship)
        ):
            return Response({'error': {'code': 'INVALID_TOKEN', 'message': 'Invitation is invalid or expired.'}}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.email.lower() != invitation.recipient_email.lower():
            return Response({'error': {'code': 'ACCOUNT_MISMATCH', 'message': 'This invitation does not belong to this account.'}}, status=status.HTTP_403_FORBIDDEN)
        if not request.user.email_verified:
            return Response({'error': {'code': 'ACCOUNT_UNVERIFIED', 'message': 'Verify your email before responding to this invitation.'}}, status=status.HTTP_400_BAD_REQUEST)

        invitation.status = BeneficiaryInvitation.Status.DECLINED
        invitation.token_hash = None
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'token_hash', 'responded_at', 'updated_at'])
        relationship.status = WillBeneficiary.Status.DECLINED
        relationship.save(update_fields=['status', 'updated_at'])

        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_invitation_declined', 'relationship_id': invitation.relationship_id, 'will_id': invitation.relationship.will_id},
        )

        return Response({'data': {'status': invitation.status}, 'message': 'Invitation declined.'})


class BeneficiaryRelationshipSelfAPIView(generics.ListAPIView):
    serializer_class = BeneficiarySelfRelationshipSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount)

    def get_queryset(self):
        return WillBeneficiary.objects.filter(
            beneficiary_user=self.request.user,
            status=WillBeneficiary.Status.ACTIVE,
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {'data': response.data}
        return response


class BeneficiaryReleaseValidateTokenAPIView(generics.GenericAPIView):
    permission_classes = ()
    serializer_class = BeneficiaryReleaseTokenSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'beneficiary_claim'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        release = get_valid_beneficiary_release(serializer.validated_data['token'])
        if not release:
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                details={'event': 'beneficiary_claim_validation_failed'},
            )
            return Response(
                {'error': {'code': 'INVALID_RELEASE_TOKEN', 'message': 'The release link is invalid or expired.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'data': {'valid': True, 'beneficiary_email': mask_email(release.allocation.beneficiary.normalized_email)}})


class BeneficiaryReleaseVerifyIdentityAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)
    serializer_class = BeneficiaryReleaseIdentityVerifySerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'beneficiary_claim'

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        release = get_valid_beneficiary_release(serializer.validated_data['token'], lock=True)
        user = request.user
        if (
            not release
            or user.account_status != User.AccountStatus.ACTIVE
            or not user.email_verified
            or release.allocation.beneficiary.normalized_email.lower() != user.email.lower()
        ):
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_identity_verification_rejected'},
            )
            return Response(
                {'error': {'code': 'INVALID_RELEASE_CLAIM', 'message': 'The release link is invalid, expired, or not assigned to this account.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relationship = WillBeneficiary.objects.select_for_update().get(pk=release.allocation.beneficiary_id)
        if relationship.identity_verification_status == WillBeneficiary.IdentityVerificationStatus.VERIFIED:
            return Response({'data': {'verified': True}, 'message': 'Beneficiary identity already verified.'})

        if (
            not relationship.identity_verification_code_hash
            or relationship.identity_verification_expires_at is None
            or relationship.identity_verification_expires_at <= timezone.now()
        ):
            code = relationship.begin_identity_verification()
            send_identity_verification_code(relationship.normalized_email, code)
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_identity_challenge_sent', 'relationship_id': relationship.pk, 'release_id': release.pk},
            )
            return Response(
                {'error': {'code': 'IDENTITY_VERIFICATION_REQUIRED', 'message': 'A verification code has been sent to your email. Enter it to continue.'}},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not relationship.verify_identity_code(serializer.validated_data['code']):
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_identity_verification_failed', 'relationship_id': relationship.pk, 'release_id': release.pk},
            )
            return Response(
                {'error': {'code': 'INVALID_IDENTITY_CODE', 'message': 'The verification code is incorrect or has expired.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=user,
            details={'event': 'beneficiary_identity_verified', 'relationship_id': relationship.pk, 'release_id': release.pk},
        )
        return Response({'data': {'verified': True}, 'message': 'Beneficiary identity verified successfully.'})


class BeneficiaryReleaseRegistrationAPIView(generics.GenericAPIView):
    permission_classes = ()
    serializer_class = BeneficiaryReleaseRegistrationSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'beneficiary_claim'

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        release = get_valid_beneficiary_release(data['token'], lock=True)
        if not release or release.allocation.beneficiary.normalized_email.lower() != data['email'].strip().lower():
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                details={'event': 'beneficiary_release_registration_rejected'},
            )
            return Response(
                {'error': {'code': 'INVALID_RELEASE_TOKEN', 'message': 'The release link or registration details are invalid.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email__iexact=data['email']).exists():
            return Response(
                {'error': {'code': 'ACCOUNT_EXISTS', 'message': 'Sign in to your existing account, then claim the release.'}},
                status=status.HTTP_409_CONFLICT,
            )

        registration_data = {
            key: data[key]
            for key in ('email', 'first_name', 'last_name', 'phone_number', 'password', 'password_confirmation')
            if key in data
        }
        registration = RegistrationSerializer(
            data=registration_data,
            context={'registration_role': User.Role.BENEFICIARY},
        )
        registration.is_valid(raise_exception=True)
        user = registration.save()
        record_beneficiary_audit(
            AuditEvent.EventType.USER_REGISTERED,
            request=request,
            target_user=user,
            details={'role': User.Role.BENEFICIARY, 'registration_source': 'authorized_beneficiary_release'},
        )
        send_email_verification(user)
        return Response(
            {'data': {'email': user.email, 'account_status': user.account_status},
             'message': 'Account created. Verify your email, then sign in and claim your authorized allocation.'},
            status=status.HTTP_201_CREATED,
        )


class BeneficiaryReleaseClaimAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)
    serializer_class = BeneficiaryReleaseTokenSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'beneficiary_claim'

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        release = get_valid_beneficiary_release(serializer.validated_data['token'], lock=True)
        user = request.user
        if (
            not release
            or user.account_status != User.AccountStatus.ACTIVE
            or not user.email_verified
            or release.allocation.beneficiary.normalized_email.lower() != user.email.lower()
        ):
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_release_claim_rejected'},
            )
            return Response(
                {'error': {'code': 'INVALID_RELEASE_CLAIM', 'message': 'The release link is invalid, expired, or not assigned to this account.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relationship = WillBeneficiary.objects.select_for_update().get(pk=release.allocation.beneficiary_id)
        if relationship.beneficiary_user_id not in (None, user.pk) or relationship.status in (
            WillBeneficiary.Status.DECLINED,
            WillBeneficiary.Status.REVOKED,
        ):
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_release_claim_conflict', 'relationship_id': relationship.pk},
            )
            return Response(
                {'error': {'code': 'INVALID_RELEASE_CLAIM', 'message': 'The release link is invalid, expired, or not assigned to this account.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if relationship.identity_verification_status != WillBeneficiary.IdentityVerificationStatus.VERIFIED:
            code = relationship.begin_identity_verification()
            send_identity_verification_code(relationship.normalized_email, code)
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=request,
                actor=user,
                details={'event': 'beneficiary_release_claim_identity_required', 'relationship_id': relationship.pk, 'release_id': release.pk},
            )
            return Response(
                {'error': {'code': 'IDENTITY_VERIFICATION_REQUIRED', 'message': 'A 6-digit verification code has been sent to your email. Verify your identity before claiming the release.'}},
                status=status.HTTP_403_FORBIDDEN,
            )

        relationship.beneficiary_user = user
        relationship.status = WillBeneficiary.Status.ACTIVE
        relationship.accepted_at = relationship.accepted_at or timezone.now()
        relationship.save(update_fields=['beneficiary_user', 'status', 'accepted_at', 'updated_at'])
        release.access_token_hash = None
        release.token_expires_at = None
        release.status = BeneficiaryRelease.Status.ACKNOWLEDGED
        release.save(update_fields=['access_token_hash', 'token_expires_at', 'status', 'updated_at'])
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=user,
            details={'event': 'beneficiary_release_claimed', 'release_id': release.pk, 'relationship_id': relationship.pk},
        )
        return Response({'data': {'claimed': True}, 'message': 'Release claimed. Your authorized allocation is available in your account.'})


class MyBeneficiaryAllocationQueryMixin:
    serializer_class = BeneficiaryAllocationAccessSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount)

    def get_queryset(self):
        return BeneficiaryAllocation.objects.filter(
            beneficiary__beneficiary_user=self.request.user,
            beneficiary__normalized_email__iexact=self.request.user.email,
            beneficiary__status=WillBeneficiary.Status.ACTIVE,
            review_status=BeneficiaryAllocation.ReviewStatus.VERIFIED,
            release_authorization__status__in=[
                BeneficiaryRelease.Status.AUTHORIZED,
                BeneficiaryRelease.Status.ACKNOWLEDGED,
            ],
            release_authorization__case__case_type=VerificationCase.CaseType.POST_DEATH_VERIFY,
            release_authorization__case__status=VerificationCase.Status.APPROVED,
            reviewed_case=F('release_authorization__case'),
        ).select_related('beneficiary__will', 'release_authorization__case')

    def mark_first_accesses(self, allocations, request):
        for allocation in allocations:
            release = allocation.release_authorization
            if not release.first_accessed_at:
                release.first_accessed_at = timezone.now()
                release.status = BeneficiaryRelease.Status.ACKNOWLEDGED
                release.save(update_fields=['first_accessed_at', 'status', 'updated_at'])
            record_beneficiary_audit(
                AuditEvent.EventType.BENEFICIARY_ALLOCATION_ACCESSED,
                request=request,
                actor=request.user,
                details={'release_id': release.pk, 'allocation_id': allocation.pk},
            )


class MyBeneficiaryAllocationsAPIView(MyBeneficiaryAllocationQueryMixin, generics.ListAPIView):
    @transaction.atomic
    def list(self, request, *args, **kwargs):
        allocations = list(self.get_queryset())
        self.mark_first_accesses(allocations, request)
        return Response({'data': self.get_serializer(allocations, many=True).data})


class MyBeneficiaryAllocationDetailAPIView(MyBeneficiaryAllocationQueryMixin, generics.RetrieveAPIView):
    def get_object(self):
        allocation = self.get_queryset().filter(pk=self.kwargs['pk']).first()
        if not allocation:
            record_beneficiary_audit(
                AuditEvent.EventType.SECURITY_ALERT,
                request=self.request,
                actor=self.request.user,
                details={'event': 'beneficiary_allocation_access_denied', 'allocation_id': self.kwargs['pk']},
            )
            raise Http404
        self.check_object_permissions(self.request, allocation)
        return allocation

    @transaction.atomic
    def retrieve(self, request, *args, **kwargs):
        allocation = self.get_object()
        self.mark_first_accesses([allocation], request)
        return Response({'data': self.get_serializer(allocation).data})
