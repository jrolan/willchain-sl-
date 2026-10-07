from rest_framework import serializers

from .models import AuditEvent


class DashboardActivitySerializer(serializers.ModelSerializer):
    event_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = ('id', 'event_type', 'event_label', 'created_at')

    def get_event_label(self, obj):
        return obj.get_event_type_display()
