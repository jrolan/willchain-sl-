from django.urls import path

from .views import (
    IntegrityOperationsAPIView,
    IntegrityRetryAPIView,
    LawyerWillIntegrityAPIView,
    WillIntegrityAPIView,
)

app_name = 'integrity'

urlpatterns = [
    path('wills/<int:will_id>/integrity/', WillIntegrityAPIView.as_view(), name='will-integrity'),
    path('wills/<int:pk>/integrity/lawyer/', LawyerWillIntegrityAPIView.as_view(), name='lawyer-will-integrity'),
    path('integrity/admin/operations/', IntegrityOperationsAPIView.as_view(), name='integrity-admin-operations'),
    path('integrity/admin/operations/<str:reference>/retry/', IntegrityRetryAPIView.as_view(), name='integrity-admin-retry'),
]
