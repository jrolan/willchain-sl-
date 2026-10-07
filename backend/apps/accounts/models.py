import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
	class Role(models.TextChoices):
		OWNER = 'OWNER', 'Will Owner'
		MEMBER = 'MEMBER', 'Member'
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
	accepted_user = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='accepted_invitations',
	)
	email = models.EmailField(db_index=True)
	first_name = models.CharField(max_length=150, blank=True)
	last_name = models.CharField(max_length=150, blank=True)
	role = models.CharField(max_length=32, choices=RoleChoices.choices)
	token_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
	status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
	message = models.TextField(blank=True)
	expires_at = models.DateTimeField()
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	accepted_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ('-created_at',)
		indexes = [
			models.Index(fields=['email', 'status'], name='accounts_in_email_0582fe_idx'),
			models.Index(fields=['token_hash', 'status'], name='accounts_in_token_a8bcde_idx'),
		]

	@staticmethod
	def generate_token():
		return secrets.token_urlsafe(32)

	@staticmethod
	def hash_token(raw_token):
		return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

	def set_token(self, raw_token):
		self.token_hash = self.hash_token(raw_token)
		if self.pk:
			self.save(update_fields=['token_hash', 'updated_at'])

	def is_valid(self):
		return self.status == self.Status.PENDING and self.expires_at > timezone.now()

	def save(self, *args, **kwargs):
		if not self.expires_at:
			self.expires_at = timezone.now() + timedelta(days=7)
		super().save(*args, **kwargs)

	def __str__(self):
		return f'{self.role} invitation to {self.email} from {self.inviter.email}'
