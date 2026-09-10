from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

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
	role = models.CharField(max_length=32, choices=Role.choices, default=Role.OWNER)
	account_status = models.CharField(
		max_length=32,
		choices=AccountStatus.choices,
		default=AccountStatus.PENDING_VERIFICATION,
	)
	email_verified = models.BooleanField(default=False)
	is_staff = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	objects = UserManager()

	def __str__(self):
		return self.email
