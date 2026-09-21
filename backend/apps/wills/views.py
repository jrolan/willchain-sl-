from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsActiveAccount, IsOwner, IsTestator
from apps.audit.models import AuditEvent
from apps.accounts.services import log_audit_event
from .models import Will
from .serializers import WillSerializer


class WillListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = WillSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, IsTestator)

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
        return Will.objects.select_related('owner')

    def get_object(self):
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])
        try:
            self.check_object_permissions(self.request, obj)
        except PermissionDenied:
            log_audit_event(
                AuditEvent.EventType.WILL_ACCESS_DENIED,
                request=self.request,
                actor=self.request.user,
                details={'will_id': obj.pk, 'operation': self.request.method},
            )
            raise
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
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
        if instance.status == Will.Status.FINALIZED:
            return Response(
                {'error': {'code': 'WILL_FINALIZED', 'message': 'This will is finalized and cannot be edited.'}},
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
        if instance.status == Will.Status.FINALIZED:
            return Response(
                {'error': {'code': 'WILL_FINALIZED', 'message': 'A finalized will cannot be deleted.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class FinalizeWillAPIView(generics.GenericAPIView):
    serializer_class = WillSerializer
    permission_classes = (IsAuthenticated, IsActiveAccount, IsOwner)

    def get_object(self):
        obj = get_object_or_404(Will.objects.select_related('owner'), pk=self.kwargs['pk'])
        try:
            self.check_object_permissions(self.request, obj)
        except PermissionDenied:
            log_audit_event(
                AuditEvent.EventType.WILL_ACCESS_DENIED,
                request=self.request,
                actor=self.request.user,
                details={'will_id': obj.pk, 'operation': 'FINALIZE'},
            )
            raise
        return obj

    def post(self, request, *args, **kwargs):
        will = self.get_object()
        if will.status == Will.Status.FINALIZED:
            return Response(
                {'error': {'code': 'WILL_ALREADY_FINALIZED', 'message': 'This will is already finalized.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        will.finalize()
        log_audit_event(
            AuditEvent.EventType.WILL_FINALIZED,
            request=request,
            actor=request.user,
            details={'will_id': will.pk, 'version': will.version, 'finalized_at': will.finalized_at.isoformat()},
        )
        return Response({'data': WillSerializer(will).data, 'message': 'Will finalized successfully.'})
