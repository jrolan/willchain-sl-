from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'actor', 'target_user', 'ip_address')
    list_filter = ('event_type', 'created_at')
    search_fields = ('actor__email', 'target_user__email', 'ip_address', 'details')
    readonly_fields = ('event_type', 'actor', 'target_user', 'ip_address', 'user_agent', 'details', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
