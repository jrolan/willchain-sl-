from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
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
from apps.wills.models import Will
from .models import BeneficiaryInvitation, WillBeneficiary
from .services import record_beneficiary_audit, send_beneficiary_invitation_email
from .serializers import (
    AcceptInvitationSerializer,
    BeneficiaryInvitationSerializer,
    BeneficiaryInvitationPreviewSerializer,
    CreateWillBeneficiarySerializer,
    BeneficiarySelfRelationshipSerializer,
    WillBeneficiarySerializer,
)


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
        invitation = relationship.invitations.order_by('-created_at').first()
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={'event': 'beneficiary_invitation_created', 'relationship_id': relationship.pk, 'invitation_id': invitation.pk, 'will_id': will.pk},
        )
        send_beneficiary_invitation_email(invitation, serializer.context['raw_invitation_token'])
        response = Response({'data': WillBeneficiarySerializer(relationship).data, 'message': 'Beneficiary invitation created successfully.'}, status=status.HTTP_201_CREATED)
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

        now = timezone.now()
        for previous_invitation in relationship.invitations.select_for_update().filter(status=BeneficiaryInvitation.Status.PENDING):
            previous_invitation.status = (
                BeneficiaryInvitation.Status.EXPIRED
                if previous_invitation.expires_at <= now
                else BeneficiaryInvitation.Status.REVOKED
            )
            previous_invitation.token_hash = None
            if previous_invitation.status == BeneficiaryInvitation.Status.REVOKED:
                previous_invitation.responded_at = now
            previous_invitation.save(update_fields=['status', 'token_hash', 'responded_at', 'updated_at'])
        raw_token = BeneficiaryInvitation.generate_token()
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            inviter=request.user,
            recipient_email=relationship.normalized_email,
            status=BeneficiaryInvitation.Status.PENDING,
            expires_at=now + timedelta(days=7),
            token_hash=BeneficiaryInvitation.hash_token(raw_token),
        )
        record_beneficiary_audit(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            details={
                'event': 'beneficiary_invitation_resent',
                'relationship_id': relationship.pk,
                'invitation_id': invitation.pk,
                'will_id': relationship.will_id,
            },
        )
        send_beneficiary_invitation_email(invitation, raw_token)
        return Response(
            {
                'data': BeneficiaryInvitationSerializer(invitation).data,
                'message': 'Beneficiary invitation resent successfully.',
            },
            status=status.HTTP_200_OK,
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
        return get_object_or_404(
            BeneficiaryInvitation.objects.select_related('relationship__will'),
            token_hash=token_hash,
            recipient_email__iexact=self.request.user.email,
            status=BeneficiaryInvitation.Status.PENDING,
            expires_at__gt=timezone.now(),
            relationship__status=WillBeneficiary.Status.PENDING,
            relationship__will__status=Will.Status.DRAFT,
        )


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
        if not invitation or not invitation.is_valid() or relationship.status != WillBeneficiary.Status.PENDING:
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
