import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
	class Role(models.TextChoices):
		OWNER = 'OWNER', 'Will Owner'
		WITNESS = 'WITNESS', 'Witness'
		BENEFICIARY = 'BENEFICIARY', 'Beneficiary'
		LAWYER_VERIFIER = 'LAWYER_VERIFIER', 'Lawyer/Authorized Verifier'
		ADMINISTRATOR = 'ADMINISTRATOR', 'System Administrator'

	class AccountStatus(models.TextChoices):
		PENDING_VERIFICATION = 'PENDING_VERIFICATION', 'Pending verification'
		ACTIVE = 'ACTIVE', 'Active'
		INACTIVE = 'INACTIVE', 'Inactive'
		SUSPENDED = 'SUSPENDED', 'Suspended'

	email = models.EmailField(unique=True)
	first_name = models.CharField(max_length=150)
	last_name = models.CharField(max_length=150)
	phone_number = models.CharField(max_length=30, blank=True)
	avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
	role = models.CharField(max_length=32, choices=Role.choices, default=Role.OWNER, db_index=True)
	account_status = models.CharField(
		max_length=32,
		choices=AccountStatus.choices,
		default=AccountStatus.PENDING_VERIFICATION,
		db_index=True,
	)
	email_verified = models.BooleanField(default=False)
	is_staff = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	objects = UserManager()

	@property
	def is_active(self):
		return self.account_status == self.AccountStatus.ACTIVE

	def __str__(self):
		return self.email


class Invitation(models.Model):
	class Status(models.TextChoices):
		PENDING = 'PENDING', 'Pending'
		ACCEPTED = 'ACCEPTED', 'Accepted'
		EXPIRED = 'EXPIRED', 'Expired'
		REVOKED = 'REVOKED', 'Revoked'

	class RoleChoices(models.TextChoices):
		WITNESS = 'WITNESS', 'Witness'
		BENEFICIARY = 'BENEFICIARY', 'Beneficiary'
		LAWYER_VERIFIER = 'LAWYER_VERIFIER', 'Lawyer/Authorized Verifier'

	inviter = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='sent_invitations',
	)
	email = models.EmailField(db_index=True)
	first_name = models.CharField(max_length=150, blank=True)
	last_name = models.CharField(max_length=150, blank=True)
	role = models.CharField(max_length=32, choices=RoleChoices.choices)
	token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
	status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
	message = models.TextField(blank=True)
	expires_at = models.DateTimeField()
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	accepted_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ('-created_at',)
		indexes = [
			models.Index(fields=['email', 'status']),
			models.Index(fields=['token', 'status']),
		]

	def is_valid(self):
		return self.status == self.Status.PENDING and self.expires_at > timezone.now()

	def save(self, *args, **kwargs):
		if not self.expires_at:
			self.expires_at = timezone.now() + timedelta(days=7)
		if not self.token:
			self.token = secrets.token_urlsafe(32)
		super().save(*args, **kwargs)

	def __str__(self):
		return f'{self.role} invitation to {self.email} from {self.inviter.email}'
