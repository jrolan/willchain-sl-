from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import CanManageOwnWills, IsActiveAccount, IsAdministrator
from apps.verification.permissions import IsAssignedLawyerOnAuthorizedCase
from apps.wills.models import Will
from .models import AnchorStatus, DocumentIntegrityRecord, WillIntegrityRecord
from .serializers import (
    IntegrityOperationsDocumentSerializer,
    IntegrityOperationsWillSerializer,
    WillIntegrityStatusSerializer,
    WillIntegrityVerificationSerializer,
)
from .services import verify_will_integrity


class WillIntegrityAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount, CanManageOwnWills)
    serializer_class = WillIntegrityStatusSerializer

    def _will(self):
        return get_object_or_404(Will.objects.filter(owner=self.request.user), pk=self.kwargs['will_id'])

    def get(self, request, *args, **kwargs):
        will = self._will()
        record = WillIntegrityRecord.objects.filter(will=will).first()
        if not record:
            return Response({
                'data': {
                    'will_id': will.pk,
                    'will_status': will.status,
                    'record': None,
                },
            })
        return Response({
            'data': {
                'will_id': will.pk,
                'will_status': will.status,
                'record': self.get_serializer(record).data,
            },
        })

    def post(self, request, *args, **kwargs):
        will = self._will()
        if will.status != Will.Status.FINALIZED:
            return Response(
                {'error': {'code': 'WILL_NOT_FINALIZED', 'message': 'Only a finalized will can be verified.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record = get_object_or_404(WillIntegrityRecord.objects.select_related('will'), will=will)
        verification = verify_will_integrity(record, request.user)
        return Response({
            'data': {
                'record': self.get_serializer(record).data,
                'verification': WillIntegrityVerificationSerializer(verification).data,
            },
        })


class LawyerWillIntegrityAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount, IsAssignedLawyerOnAuthorizedCase)
    serializer_class = WillIntegrityStatusSerializer

    def get(self, request, *args, **kwargs):
        record = get_object_or_404(
            WillIntegrityRecord.objects.select_related('will'),
            will_id=self.kwargs['pk'],
        )
        serializer = self.get_serializer(record, context={'hide_documents': True})
        return Response({'data': serializer.data})

    def post(self, request, *args, **kwargs):
        record = get_object_or_404(
            WillIntegrityRecord.objects.select_related('will'),
            will_id=self.kwargs['pk'],
        )
        verification = verify_will_integrity(record, request.user)
        return Response({
            'data': {
                'record': self.get_serializer(record, context={'hide_documents': True}).data,
                'verification': WillIntegrityVerificationSerializer(
                    verification,
                    context={'hide_documents': True},
                ).data,
            },
        })


class IntegrityOperationsAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount, IsAdministrator)

    def get(self, request, *args, **kwargs):
        wills = WillIntegrityRecord.objects.exclude(anchor_status=AnchorStatus.CONFIRMED).order_by('updated_at')[:100]
        documents = DocumentIntegrityRecord.objects.exclude(anchor_status=AnchorStatus.CONFIRMED).order_by('updated_at')[:100]
        return Response({
            'data': {
                'wills': IntegrityOperationsWillSerializer(wills, many=True).data,
                'documents': IntegrityOperationsDocumentSerializer(documents, many=True).data,
            },
        })


class IntegrityRetryAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount, IsAdministrator)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        reference = self.kwargs['reference']
        record = (
            WillIntegrityRecord.objects.select_for_update().filter(record_reference=reference).first()
            or DocumentIntegrityRecord.objects.select_for_update().filter(record_reference=reference).first()
        )
        if not record:
            return Response({'error': {'code': 'NOT_FOUND', 'message': 'Integrity operation not found.'}}, status=404)
        if record.anchor_status != AnchorStatus.FAILED:
            return Response(
                {'error': {'code': 'NOT_RETRYABLE', 'message': 'Only failed integrity operations can be retried.'}},
                status=status.HTTP_409_CONFLICT,
            )
        if isinstance(record, DocumentIntegrityRecord) and not record.commitment:
            return Response(
                {'error': {'code': 'DOCUMENT_NOT_VERIFIED', 'message': 'This document cannot be anchored because its stored bytes did not pass the integrity check.'}},
                status=status.HTTP_409_CONFLICT,
            )
        record.anchor_status = AnchorStatus.QUEUED
        record.transaction_hash = ''
        record.block_number = None
        record.confirmations = 0
        record.encrypted_raw_transaction = ''
        record.submitted_at = None
        record.confirmed_at = None
        record.last_error_code = ''
        record.save(update_fields=(
            'anchor_status',
            'transaction_hash',
            'block_number',
            'confirmations',
            'encrypted_raw_transaction',
            'submitted_at',
            'confirmed_at',
            'last_error_code',
            'updated_at',
        ))
        return Response({'data': {'record_reference': record.record_reference, 'anchor_status': record.anchor_status}})
