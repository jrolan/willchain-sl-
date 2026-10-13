from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsActiveAccount, IsAdministrator
from apps.audit.models import AuditEvent
from apps.wills.models import Will
from .models import DocumentIntegrityCheck, WillDocument
from .serializers import (
    AdminDocumentMetadataSerializer,
    DocumentIntegrityCheckSerializer,
    DocumentMetadataUpdateSerializer,
    WillDocumentSerializer,
)
from .services import (
    create_document,
    record_document_audit,
    replace_document,
    soft_delete_document,
    update_document_metadata,
    verify_document_integrity,
)
from .storage import PrivateStorageError, private_document_storage
from .validation import MAX_DOCUMENT_SIZE_BYTES, validate_upload


class DocumentAPIView(GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount)

    @staticmethod
    def not_found():
        return Response({'error': {'code': 'NOT_FOUND', 'message': 'Document resource not found.'}}, status=status.HTTP_404_NOT_FOUND)

    def get_will(self, request, *, lock=False):
        queryset = Will.objects
        if lock:
            queryset = queryset.select_for_update()
        will = queryset.filter(pk=self.kwargs['will_id'], owner=request.user).first()
        if not will or request.user.role == User.Role.ADMINISTRATOR:
            record_document_audit(
                request=request,
                actor=request.user,
                will_id=self.kwargs['will_id'],
                document_id=None,
                action='ACCESS_DENIED',
                outcome='DENIED',
            )
            return None
        return will

    def get_document(self, request, will, *, lock=False, active_only=True):
        queryset = WillDocument.objects.select_related('will')
        if lock:
            queryset = queryset.select_for_update()
        filters = {'pk': self.kwargs['pk'], 'will': will}
        if active_only:
            filters.update(status=WillDocument.Status.ACTIVE, deleted_at__isnull=True)
        document = queryset.filter(**filters).first()
        if not document:
            record_document_audit(
                request=request,
                actor=request.user,
                will_id=will.pk,
                document_id=self.kwargs['pk'],
                action='ACCESS_DENIED',
                outcome='DENIED',
            )
            return None
        return document

    def ensure_draft(self, will):
        if will.status != Will.Status.DRAFT:
            return Response(
                {'error': {'code': 'WILL_NOT_DRAFT', 'message': 'Document changes are allowed only while the will is a draft.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None


class WillDocumentListCreateAPIView(DocumentAPIView):
    def get(self, request, *args, **kwargs):
        will = self.get_will(request)
        if will is None:
            return self.not_found()
        documents = WillDocument.objects.filter(
            will=will, status=WillDocument.Status.ACTIVE, deleted_at__isnull=True
        )
        return Response({
            'data': WillDocumentSerializer(documents, many=True).data,
            'max_file_size_bytes': MAX_DOCUMENT_SIZE_BYTES,
        })

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        will = self.get_will(request, lock=True)
        if will is None:
            return self.not_found()
        lifecycle_error = self.ensure_draft(will)
        if lifecycle_error:
            return lifecycle_error
        validated = validate_upload(request.FILES.get('file'))
        document_type = request.data.get('document_type')
        if document_type not in WillDocument.DocumentType.values:
            return Response({'document_type': ['A valid document type is required.']}, status=status.HTTP_400_BAD_REQUEST)
        description = request.data.get('description', '')
        if not isinstance(description, str) or len(description) > 255:
            return Response({'description': ['Ensure this field has no more than 255 characters.']}, status=status.HTTP_400_BAD_REQUEST)
        document = create_document(
            will=will,
            actor=request.user,
            request=request,
            validated=validated,
            document_type=document_type,
            description=description,
        )
        return Response(
            {'data': WillDocumentSerializer(document).data, 'message': 'Document uploaded successfully.'},
            status=status.HTTP_201_CREATED,
        )


class WillDocumentDetailAPIView(DocumentAPIView):
    def get(self, request, *args, **kwargs):
        will = self.get_will(request)
        if will is None:
            return self.not_found()
        document = self.get_document(request, will)
        if document is None:
            return self.not_found()
        return Response({'data': WillDocumentSerializer(document).data})

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        will = self.get_will(request, lock=True)
        if will is None:
            return self.not_found()
        lifecycle_error = self.ensure_draft(will)
        if lifecycle_error:
            return lifecycle_error
        document = self.get_document(request, will, lock=True)
        if document is None:
            return self.not_found()
        serializer = DocumentMetadataUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_document_metadata(
            document=document,
            actor=request.user,
            request=request,
            values=serializer.validated_data,
        )
        return Response({'data': WillDocumentSerializer(document).data, 'message': 'Document metadata updated.'})

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        will = self.get_will(request, lock=True)
        if will is None:
            return self.not_found()
        lifecycle_error = self.ensure_draft(will)
        if lifecycle_error:
            return lifecycle_error
        document = self.get_document(request, will, lock=True)
        if document is None:
            return self.not_found()
        soft_delete_document(document=document, actor=request.user, request=request)
        return Response({'data': {'id': document.pk, 'status': document.status}, 'message': 'Document deleted.'})


class WillDocumentReplaceAPIView(DocumentAPIView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        will = self.get_will(request, lock=True)
        if will is None:
            return self.not_found()
        lifecycle_error = self.ensure_draft(will)
        if lifecycle_error:
            return lifecycle_error
        previous = self.get_document(request, will, lock=True)
        if previous is None:
            return self.not_found()
        validated = validate_upload(request.FILES.get('file'))
        replacement = replace_document(previous=previous, actor=request.user, request=request, validated=validated)
        return Response(
            {'data': WillDocumentSerializer(replacement).data, 'message': 'Document replaced with a new version.'},
            status=status.HTTP_201_CREATED,
        )


class WillDocumentVersionsAPIView(DocumentAPIView):
    def get(self, request, *args, **kwargs):
        will = self.get_will(request)
        if will is None:
            return self.not_found()
        document = self.get_document(request, will, active_only=False)
        if document is None:
            return self.not_found()
        versions = WillDocument.objects.filter(will=will, version_group=document.version_group).order_by('version')
        return Response({'data': WillDocumentSerializer(versions, many=True).data})


class WillDocumentIntegrityAPIView(DocumentAPIView):
    @transaction.atomic
    def get(self, request, *args, **kwargs):
        will = self.get_will(request, lock=True)
        if will is None:
            return self.not_found()
        document = self.get_document(request, will, active_only=False)
        if document is None:
            return self.not_found()
        checks = document.integrity_checks.select_related('actor').all()
        return Response({'data': DocumentIntegrityCheckSerializer(checks, many=True).data})

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        will = self.get_will(request, lock=True)
        if will is None:
            return self.not_found()
        document = self.get_document(request, will, lock=True, active_only=False)
        if document is None:
            return self.not_found()
        if document.status == WillDocument.Status.DELETED:
            record_document_audit(
                request=request,
                actor=request.user,
                will_id=will.pk,
                document_id=document.pk,
                action='ACCESS_DENIED',
                outcome='DENIED',
            )
            return self.not_found()
        check = verify_document_integrity(document=document, actor=request.user, request=request)
        return Response(
            {'data': DocumentIntegrityCheckSerializer(check).data, 'message': 'Integrity check recorded.'},
            status=status.HTTP_201_CREATED,
        )


class WillDocumentDownloadAPIView(DocumentAPIView):
    def get(self, request, *args, **kwargs):
        will = self.get_will(request)
        if will is None:
            return self.not_found()
        document = self.get_document(request, will)
        if document is None:
            return self.not_found()
        try:
            source = private_document_storage.open(document.storage_key)
        except PrivateStorageError:
            record_document_audit(
                request=request,
                actor=request.user,
                will_id=will.pk,
                document_id=document.pk,
                action='DOWNLOAD',
                outcome='STORAGE_ERROR',
            )
            return Response({'error': {'code': 'DOCUMENT_UNAVAILABLE', 'message': 'The document is unavailable.'}}, status=status.HTTP_404_NOT_FOUND)
        try:
            record_document_audit(
                request=request,
                actor=request.user,
                will_id=will.pk,
                document_id=document.pk,
                action='DOWNLOAD',
            )
        except Exception:
            source.close()
            raise
        response = FileResponse(source, content_type=document.media_type, as_attachment=True)
        response['Content-Disposition'] = content_disposition_header(True, document.original_filename)
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'private, no-store'
        return response


class AdminDocumentMetadataAPIView(GenericAPIView):
    permission_classes = (IsAuthenticated, IsActiveAccount, IsAdministrator)

    def get(self, request, *args, **kwargs):
        documents = WillDocument.objects.all().order_by('-created_at')[:100]
        return Response({'data': AdminDocumentMetadataSerializer(documents, many=True).data})