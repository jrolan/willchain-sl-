from django.urls import path

from .views import (
    BeneficiaryInvitationAcceptAPIView,
    BeneficiaryInvitationDeclineAPIView,
    BeneficiaryInvitationPreviewAPIView,
    BeneficiaryInvitationRegistrationAPIView,
    BeneficiaryInvitationResendAPIView,
    BeneficiaryReleaseClaimAPIView,
    BeneficiaryReleaseRegistrationAPIView,
    BeneficiaryReleaseValidateTokenAPIView,
    MyBeneficiaryAllocationDetailAPIView,
    MyBeneficiaryAllocationsAPIView,
    BeneficiaryRelationshipSelfAPIView,
    WillBeneficiaryAllocationDetailAPIView,
    WillBeneficiaryAllocationListCreateAPIView,
    WillBeneficiaryDetailAPIView,
    WillBeneficiaryListCreateAPIView,
)

app_name = 'beneficiaries'

urlpatterns = [
    path('wills/<int:will_id>/beneficiaries/', WillBeneficiaryListCreateAPIView.as_view(), name='will-beneficiaries'),
    path('wills/<int:will_id>/beneficiaries/<int:pk>/', WillBeneficiaryDetailAPIView.as_view(), name='will-beneficiary-detail'),
    path('wills/<int:will_id>/beneficiaries/<int:beneficiary_id>/allocations/', WillBeneficiaryAllocationListCreateAPIView.as_view(), name='will-beneficiary-allocations'),
    path('wills/<int:will_id>/beneficiaries/<int:beneficiary_id>/allocations/<int:pk>/', WillBeneficiaryAllocationDetailAPIView.as_view(), name='will-beneficiary-allocation-detail'),
    path('wills/<int:will_id>/beneficiaries/<int:pk>/resend-invitation/', BeneficiaryInvitationResendAPIView.as_view(), name='resend-beneficiary-invitation'),
    path('beneficiary-invitations/accept/', BeneficiaryInvitationAcceptAPIView.as_view(), name='accept-invitation'),
    path('beneficiary-invitations/decline/', BeneficiaryInvitationDeclineAPIView.as_view(), name='decline-invitation'),
    path('beneficiary-invitations/register/', BeneficiaryInvitationRegistrationAPIView.as_view(), name='register-from-invitation'),
    path('beneficiary-invitations/<str:token>/', BeneficiaryInvitationPreviewAPIView.as_view(), name='beneficiary-invitation-preview'),
    path('me/beneficiary-relationships/', BeneficiaryRelationshipSelfAPIView.as_view(), name='my-beneficiary-relationships'),
    path('beneficiary-release/validate-token/', BeneficiaryReleaseValidateTokenAPIView.as_view(), name='beneficiary-release-validate-token'),
    path('beneficiary-release/register/', BeneficiaryReleaseRegistrationAPIView.as_view(), name='beneficiary-release-register'),
    path('beneficiary-release/claim/', BeneficiaryReleaseClaimAPIView.as_view(), name='beneficiary-release-claim'),
    path('me/beneficiary-allocations/', MyBeneficiaryAllocationsAPIView.as_view(), name='my-beneficiary-allocations'),
    path('me/beneficiary-allocations/<int:pk>/', MyBeneficiaryAllocationDetailAPIView.as_view(), name='my-beneficiary-allocation-detail'),
]
