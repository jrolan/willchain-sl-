from django.urls import path

from .views import FinalizeWillAPIView, WillDetailAPIView, WillListCreateAPIView

app_name = 'wills'

urlpatterns = [
    path('', WillListCreateAPIView.as_view(), name='will-list'),
    path('<int:pk>/', WillDetailAPIView.as_view(), name='will-detail'),
    path('<int:pk>/finalize/', FinalizeWillAPIView.as_view(), name='will-finalize'),
]
