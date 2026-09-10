from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class AccountUserAdmin(UserAdmin):
	ordering = ('email',)
	list_display = ('email', 'role', 'account_status', 'email_verified', 'is_staff')
	list_filter = ('role', 'account_status', 'email_verified', 'is_staff')
	search_fields = ('email', 'first_name', 'last_name')
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Identity', {'fields': ('first_name', 'last_name', 'phone_number')}),
		('Access', {'fields': ('role', 'account_status', 'email_verified')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
	)
	add_fieldsets = (
		(None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),
	)
