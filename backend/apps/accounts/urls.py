from django.urls import path

from .views import (
    AcceptInvitationView,
    ChangePasswordView,
    ForgotPasswordView,
    GoogleLinkView,
    GoogleLoginView,
    GoogleUnlinkView,
    InvitationListView,
    LoginView,
    LogoutView,
    MyCollaborationsView,
    MeView,
    RefreshView,
    RegisterView,
    ResetPasswordView,
    VerifyEmailView,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('google/login/', GoogleLoginView.as_view(), name='google-login'),
    path('google/link/', GoogleLinkView.as_view(), name='google-link'),
    path('google/unlink/', GoogleUnlinkView.as_view(), name='google-unlink'),
    path('token/refresh/', RefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('invitations/', InvitationListView.as_view(), name='invitations'),
    path('my-collaborations/', MyCollaborationsView.as_view(), name='my-collaborations'),
    path('invitations/accept/', AcceptInvitationView.as_view(), name='accept-invitation'),
]
