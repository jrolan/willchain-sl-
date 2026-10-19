from django.urls import path

from .views import (
    CaseAssignLawyerAPIView,
    CaseBeginReviewAPIView,
    CaseDecisionAPIView,
    CaseEligibilityAPIView,
    CaseEvidenceDownloadAPIView,
    CaseEvidenceListCreateAPIView,
    CaseEvidenceSufficiencyAPIView,
    CaseInformationRequestAPIView,
    CaseResubmitAPIView,
    CaseSubmitAPIView,
    CaseWithdrawAPIView,
    Module8VerificationStatusAPIView,
    VerificationCaseDetailAPIView,
    VerificationCaseListCreateAPIView,
    WillDisclosureAuthorizeAPIView,
    WillDisclosureDownloadAPIView,
    WillDisclosureRevokeAPIView,
)

app_name = 'verification'

urlpatterns = [
    path('cases/', VerificationCaseListCreateAPIView.as_view(), name='case-list'),
    path('cases/<int:pk>/', VerificationCaseDetailAPIView.as_view(), name='case-detail'),
    path('cases/<int:pk>/submit/', CaseSubmitAPIView.as_view(), name='case-submit'),
    path('cases/<int:pk>/assign-lawyer/', CaseAssignLawyerAPIView.as_view(), name='case-assign-lawyer'),
    path('cases/<int:pk>/assess-eligibility/', CaseEligibilityAPIView.as_view(), name='case-assess-eligibility'),
    path('cases/<int:pk>/evidence/', CaseEvidenceListCreateAPIView.as_view(), name='case-evidence'),
    path('cases/<int:pk>/evidence/<int:evidence_pk>/download/', CaseEvidenceDownloadAPIView.as_view(), name='case-evidence-download'),
    path('cases/<int:pk>/evidence/<int:evidence_pk>/sufficiency/', CaseEvidenceSufficiencyAPIView.as_view(), name='case-evidence-sufficiency'),
    path('cases/<int:pk>/begin-review/', CaseBeginReviewAPIView.as_view(), name='case-begin-review'),
    path('cases/<int:pk>/request-information/', CaseInformationRequestAPIView.as_view(), name='case-request-information'),
    path('cases/<int:pk>/resubmit/', CaseResubmitAPIView.as_view(), name='case-resubmit'),
    path('cases/<int:pk>/decision/', CaseDecisionAPIView.as_view(), name='case-decision'),
    path('cases/<int:pk>/withdraw/', CaseWithdrawAPIView.as_view(), name='case-withdraw'),
    path('cases/<int:pk>/authorize-disclosure/', WillDisclosureAuthorizeAPIView.as_view(), name='case-authorize-disclosure'),
    path('cases/<int:pk>/revoke-disclosure/', WillDisclosureRevokeAPIView.as_view(), name='case-revoke-disclosure'),
    path('cases/<int:pk>/disclosure-download/', WillDisclosureDownloadAPIView.as_view(), name='case-disclosure-download'),
    path('status/<int:will_pk>/', Module8VerificationStatusAPIView.as_view(), name='will-verification-status'),
]
