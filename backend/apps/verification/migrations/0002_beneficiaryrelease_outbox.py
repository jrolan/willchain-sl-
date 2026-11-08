import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_user_google_sub'),
        ('beneficiaries', '0002_beneficiaryallocation'),
        ('verification', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BeneficiaryRelease',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('AUTHORIZED', 'Authorized'), ('REVOKED', 'Revoked'), ('ACKNOWLEDGED', 'Claimed')], db_index=True, default='AUTHORIZED', max_length=16)),
                ('authorized_at', models.DateTimeField(auto_now_add=True)),
                ('access_token_hash', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('first_accessed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('allocation', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='release_authorization', to='beneficiaries.beneficiaryallocation')),
                ('authorized_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='authorized_beneficiary_releases', to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='beneficiary_releases', to='verification.verificationcase')),
            ],
            options={
                'ordering': ('-authorized_at',),
                'indexes': [
                    models.Index(fields=['case', 'status'], name='release_case_status_idx'),
                    models.Index(fields=['status', 'token_expires_at'], name='release_status_exp_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='BeneficiaryNotificationOutbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('DELIVERED', 'Delivered'), ('FAILED', 'Failed')], db_index=True, default='PENDING', max_length=16)),
                ('idempotency_key', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('available_at', models.DateTimeField(db_index=True)),
                ('last_error', models.CharField(blank=True, max_length=128)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('release', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification', to='verification.beneficiaryrelease')),
            ],
            options={
                'ordering': ('created_at',),
                'indexes': [models.Index(fields=['status', 'available_at'], name='notify_status_avail_idx')],
            },
        ),
    ]
