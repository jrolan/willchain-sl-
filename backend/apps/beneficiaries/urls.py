from django.urls import path

from .views import (
    BeneficiaryInvitationAcceptAPIView,
    BeneficiaryInvitationDeclineAPIView,
    BeneficiaryInvitationPreviewAPIView,
    BeneficiaryInvitationRegistrationAPIView,
    BeneficiaryInvitationResendAPIView,
    BeneficiaryRelationshipSelfAPIView,
    WillBeneficiaryDetailAPIView,
    WillBeneficiaryListCreateAPIView,
)

app_name = 'beneficiaries'

urlpatterns = [
    path('wills/<int:will_id>/beneficiaries/', WillBeneficiaryListCreateAPIView.as_view(), name='will-beneficiaries'),
    path('wills/<int:will_id>/beneficiaries/<int:pk>/', WillBeneficiaryDetailAPIView.as_view(), name='will-beneficiary-detail'),
    path('wills/<int:will_id>/beneficiaries/<int:pk>/resend-invitation/', BeneficiaryInvitationResendAPIView.as_view(), name='resend-beneficiary-invitation'),
    path('beneficiary-invitations/accept/', BeneficiaryInvitationAcceptAPIView.as_view(), name='accept-invitation'),
    path('beneficiary-invitations/decline/', BeneficiaryInvitationDeclineAPIView.as_view(), name='decline-invitation'),
    path('beneficiary-invitations/register/', BeneficiaryInvitationRegistrationAPIView.as_view(), name='register-from-invitation'),
    path('beneficiary-invitations/<str:token>/', BeneficiaryInvitationPreviewAPIView.as_view(), name='beneficiary-invitation-preview'),
    path('me/beneficiary-relationships/', BeneficiaryRelationshipSelfAPIView.as_view(), name='my-beneficiary-relationships'),
]
