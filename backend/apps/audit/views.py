from django.db.models import Q
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsActiveAccount
from .models import AuditEvent
from .serializers import DashboardActivitySerializer


class MyActivityListAPIView(ListAPIView):
    serializer_class = DashboardActivitySerializer
    permission_classes = (IsAuthenticated, IsActiveAccount)

    def get_queryset(self):
        return AuditEvent.objects.filter(
            Q(actor=self.request.user) | Q(target_user=self.request.user),
        ).select_related('actor', 'target_user').order_by('-created_at')[:10]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {'data': response.data}
        return response
