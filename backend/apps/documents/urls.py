from django.urls import path

from .views import AdminDocumentMetadataAPIView

app_name = 'documents'

urlpatterns = [
    path('admin/documents/metadata/', AdminDocumentMetadataAPIView.as_view(), name='admin-document-metadata'),
]