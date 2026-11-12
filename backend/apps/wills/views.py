from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Invitation
from apps.accounts.permissions import CanManageOwnWills, IsActiveAccount, IsOwner
from apps.audit.models import AuditEvent
from apps.accounts.services import log_audit_event
from apps.verification.models import VerificationCase
from apps.verification.permissions import IsAssignedLawyerOnAuthorizedCase
from apps.integrity.services import create_will_integrity_record
from .models import Will, WitnessAttestation
from .serializers import LawyerWillReadOnlySerializer, WillSerializer, WitnessAttestationInputSerializer, WitnessAssignmentSerializer


class WillListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = WillSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills)

    def get_queryset(self):
        return Will.objects.filter(owner=self.request.user).select_related('owner')

    def perform_create(self, serializer):
        will = serializer.save(owner=self.request.user)
        log_audit_event(
            AuditEvent.EventType.WILL_CREATED,
            request=self.request,
            actor=self.request.user,
            details={'will_id': will.pk, 'version': will.version},
        )
        return will

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {'data': response.data}
        return response

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data = {'data': response.data, 'message': 'Will draft created successfully.'}
        return response


class WillDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WillSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, IsOwner)

    def get_queryset(self):
        return Will.objects.filter(owner=self.request.user).select_related('owner')

    def get_object(self):
        pk = self.kwargs['pk']
        obj = Will.objects.filter(owner=self.request.user, pk=pk).select_related('owner').first()
        if not obj:
            # Audit unauthorized IDOR attempt if the object exists for another user
            other_obj = Will.objects.filter(pk=pk).first()
            if other_obj:
                log_audit_event(
                    AuditEvent.EventType.WILL_ACCESS_DENIED,
                    request=self.request,
                    actor=self.request.user,
                    details={'will_id': other_obj.pk, 'operation': self.request.method},
                )
            raise Http404('No Will matches the given query.')
        self.check_object_permissions(self.request, obj)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Finalized and archived wills remain readable to the owner, but they are no
        # longer mutable. The mutation checks live in update()/destroy() below.
        log_audit_event(
            AuditEvent.EventType.WILL_ACCESSED,
            request=request,
            actor=request.user,
            details={'will_id': instance.pk, 'status': instance.status},
        )
        serializer = self.get_serializer(instance)
        return Response({'data': serializer.data})

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_editable:
            is_finalized = instance.status == Will.Status.FINALIZED
            return Response(
                {
                    'error': {
                        'code': 'WILL_FINALIZED' if is_finalized else 'WILL_NOT_EDITABLE',
                        'message': 'This will is finalized and cannot be edited.' if is_finalized else 'Only draft wills can be edited.',
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = super().update(request, *args, **kwargs)
        log_audit_event(
            AuditEvent.EventType.WILL_UPDATED,
            request=request,
            actor=request.user,
            details={'will_id': instance.pk, 'version': instance.version},
        )
        response.data = {'data': response.data, 'message': 'Will draft updated successfully.'}
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_editable:
            is_finalized = instance.status == Will.Status.FINALIZED
            return Response(
                {
                    'error': {
                        'code': 'WILL_FINALIZED' if is_finalized else 'WILL_NOT_EDITABLE',
                        'message': 'A finalized will cannot be deleted.' if is_finalized else 'Only draft wills can be deleted.',
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = super().destroy(request, *args, **kwargs)
        log_audit_event(
            AuditEvent.EventType.WILL_DELETED,
            request=request,
            actor=request.user,
            details={'will_id': instance.pk, 'version': instance.version},
        )
        return response


class LawyerWillViewAPIView(generics.RetrieveAPIView):
    serializer_class = LawyerWillReadOnlySerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, IsAssignedLawyerOnAuthorizedCase)

    def get_queryset(self):
        eligible_case = VerificationCase.objects.filter(
            will_id=OuterRef('pk'),
            assigned_lawyer=self.request.user,
            status__in=[
                VerificationCase.Status.OPEN,
                VerificationCase.Status.INFORMATION_REQUIRED,
                VerificationCase.Status.UNDER_REVIEW,
                VerificationCase.Status.APPROVED,
            ],
        ).filter(
            Q(case_type=VerificationCase.CaseType.POST_DEATH_VERIFY)
            | Q(
                case_type=VerificationCase.CaseType.PRE_DEATH_REVIEW,
                disclosure_authorization__is_active=True,
            )
        )
        return Will.objects.filter(pk=self.kwargs['pk']).filter(Exists(eligible_case)).select_related('owner')

    def get_object(self):
        obj = self.get_queryset().first()
        if not obj:
            raise Http404('No authorized will view is available for this lawyer.')
        self.check_object_permissions(self.request, obj)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        log_audit_event(
            AuditEvent.EventType.WILL_ACCESSED,
            request=request,
            actor=request.user,
            details={'will_id': instance.pk, 'status': instance.status, 'access_scope': 'LAWYER_READ_ONLY'},
        )
        serializer = self.get_serializer(instance)
        return Response({'data': serializer.data})


class MyWitnessAssignmentsAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)
    serializer_class = WitnessAssignmentSerializer

    def get(self, request, *args, **kwargs):
        invitations = Invitation.objects.filter(
            accepted_user=request.user,
            status=Invitation.Status.ACCEPTED,
            role=Invitation.RoleChoices.WITNESS,
            will__isnull=False,
        ).select_related('will').order_by('-created_at')
        assignments = []
        for invitation in invitations:
            attestation = getattr(invitation, 'witness_attestation', None)
            assignments.append({
                'invitation_id': invitation.pk,
                'will_id': invitation.will_id,
                'will_title': invitation.will.title,
                'will_status': invitation.will.status,
                'will_version': invitation.will.version,
                'attestation_status': (
                    attestation.status if attestation else
                    'PENDING' if invitation.will.status == Will.Status.FINALIZED else
                    'NOT_READY'
                ),
                'responded_at': attestation.responded_at if attestation else None,
                'attested_version': attestation.will_version if attestation else None,
            })
        return Response({'data': self.get_serializer(assignments, many=True).data})


class WitnessAttestationAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)
    serializer_class = WitnessAttestationInputSerializer

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        invitation = Invitation.objects.select_for_update().filter(
            pk=pk,
            accepted_user=request.user,
            status=Invitation.Status.ACCEPTED,
            role=Invitation.RoleChoices.WITNESS,
            will__isnull=False,
        ).select_related('will').first()
        if not invitation:
            raise NotFound('Witness assignment not found.')
        if invitation.will.status != Will.Status.FINALIZED:
            raise ValidationError('Witness attestation is available only for a finalized will.')
        if WitnessAttestation.objects.filter(invitation=invitation).exists():
            return Response(
                {'error': {'code': 'ATTESTATION_ALREADY_RECORDED', 'message': 'A witness response has already been recorded.'}},
                status=status.HTTP_409_CONFLICT,
            )

        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        attestation = WitnessAttestation.objects.create(
            invitation=invitation,
            will=invitation.will,
            witness=request.user,
            status=input_serializer.validated_data['decision'],
            will_version=invitation.will.version,
            will_content_hash=WitnessAttestation.hash_will_content(invitation.will.content),
        )
        log_audit_event(
            AuditEvent.EventType.SECURITY_ALERT,
            request=request,
            actor=request.user,
            target_user=invitation.inviter,
            details={
                'event': 'witness_attestation_recorded',
                'attestation_id': attestation.pk,
                'invitation_id': invitation.pk,
                'will_id': invitation.will_id,
                'will_version': attestation.will_version,
                'decision': attestation.status,
                'will_content_hash': attestation.will_content_hash,
            },
        )
        return Response({
            'data': {
                'invitation_id': invitation.pk,
                'will_id': invitation.will_id,
                'status': attestation.status,
                'will_version': attestation.will_version,
                'responded_at': attestation.responded_at,
            },
            'message': 'Your witness response has been recorded. This record is not an electronic signature or legal validation.',
        }, status=status.HTTP_201_CREATED)


class FinalizeWillAPIView(generics.GenericAPIView):
    serializer_class = WillSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, IsOwner)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        # Row-level pessimistic locking within atomic transaction to prevent double-submit race condition
        will = Will.objects.select_for_update().filter(owner=request.user, pk=pk).select_related('owner').first()
        if not will:
            other_will = Will.objects.filter(pk=pk).first()
            if other_will:
                log_audit_event(
                    AuditEvent.EventType.WILL_ACCESS_DENIED,
                    request=self.request,
                    actor=self.request.user,
                    details={'will_id': other_will.pk, 'operation': 'FINALIZE'},
                )
            return Response(
                {'error': {'code': 'NOT_FOUND', 'message': 'Will not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if will.status == Will.Status.FINALIZED:
            return Response(
                {'error': {'code': 'WILL_ALREADY_FINALIZED', 'message': 'This will is already finalized.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        will.finalize()
        create_will_integrity_record(will)
        log_audit_event(
            AuditEvent.EventType.WILL_FINALIZED,
            request=request,
            actor=request.user,
            details={'will_id': will.pk, 'version': will.version, 'finalized_at': will.finalized_at.isoformat()},
        )
        return Response({'data': WillSerializer(will).data, 'message': 'Will finalized successfully.'})
