from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Invitation, User


@admin.register(User)
class AccountUserAdmin(UserAdmin):
	ordering = ('email',)
	list_display = ('email', 'role', 'account_status', 'email_verified', 'is_active', 'is_staff')
	list_filter = ('role', 'account_status', 'email_verified', 'is_staff')
	search_fields = ('email', 'first_name', 'last_name')
	readonly_fields = ('is_active', 'created_at', 'updated_at')
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Identity', {'fields': ('first_name', 'last_name', 'phone_number', 'avatar')}),
		('Access', {'fields': ('role', 'account_status', 'email_verified', 'is_active')}),
		('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		('Timestamps', {'fields': ('created_at', 'updated_at')}),
	)
	add_fieldsets = (
		(None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),
	)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
	list_display = ('email', 'role', 'inviter', 'status', 'expires_at', 'created_at')
	list_filter = ('role', 'status', 'created_at')
	search_fields = ('email', 'inviter__email', 'first_name', 'last_name')
	readonly_fields = ('token', 'created_at', 'updated_at', 'accepted_at')
