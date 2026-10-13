from django.urls import path

from apps.documents.views import (
    WillDocumentDetailAPIView,
    WillDocumentDownloadAPIView,
    WillDocumentIntegrityAPIView,
    WillDocumentListCreateAPIView,
    WillDocumentReplaceAPIView,
    WillDocumentVersionsAPIView,
)
from .views import FinalizeWillAPIView, WillDetailAPIView, WillListCreateAPIView

app_name = 'wills'

urlpatterns = [
    path('', WillListCreateAPIView.as_view(), name='will-list'),
    path('<int:pk>/', WillDetailAPIView.as_view(), name='will-detail'),
    path('<int:pk>/finalize/', FinalizeWillAPIView.as_view(), name='will-finalize'),
    path('<int:will_id>/documents/', WillDocumentListCreateAPIView.as_view(), name='will-documents'),
    path('<int:will_id>/documents/<int:pk>/', WillDocumentDetailAPIView.as_view(), name='will-document-detail'),
    path('<int:will_id>/documents/<int:pk>/download/', WillDocumentDownloadAPIView.as_view(), name='will-document-download'),
    path('<int:will_id>/documents/<int:pk>/replace/', WillDocumentReplaceAPIView.as_view(), name='will-document-replace'),
    path('<int:will_id>/documents/<int:pk>/versions/', WillDocumentVersionsAPIView.as_view(), name='will-document-versions'),
    path('<int:will_id>/documents/<int:pk>/integrity-checks/', WillDocumentIntegrityAPIView.as_view(), name='will-document-integrity'),
]
