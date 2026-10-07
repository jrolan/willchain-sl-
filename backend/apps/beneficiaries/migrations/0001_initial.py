import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('accounts', '0004_user_member_role'),
        ('wills', '0003_alter_will_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='WillBeneficiary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('normalized_email', models.EmailField(db_index=True, max_length=254)),
                ('full_name', models.CharField(blank=True, max_length=200)),
                ('relationship_type', models.CharField(choices=[('PRIMARY', 'Primary'), ('CONTINGENT', 'Contingent'), ('RESIDUAL', 'Residual'), ('WITNESS', 'Witness'), ('LAWYER', 'Lawyer')], default='PRIMARY', max_length=32)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('ACTIVE', 'Active'), ('DECLINED', 'Declined'), ('REVOKED', 'Revoked')], db_index=True, default='PENDING', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('beneficiary_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='beneficiary_relationships', to=settings.AUTH_USER_MODEL)),
                ('will', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='beneficiaries', to='wills.will')),
            ],
            options={
                'ordering': ('-created_at',),
                'indexes': [
                    models.Index(fields=['will', 'status'], name='ben_will_status_idx'),
                    models.Index(fields=['beneficiary_user', 'status'], name='ben_user_status_idx'),
                    models.Index(fields=['normalized_email', 'status'], name='ben_email_status_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(condition=Q(status__in=['PENDING', 'ACTIVE']), fields=('will', 'normalized_email'), name='unique_active_or_pending_beneficiary_email_per_will'),
                    models.UniqueConstraint(condition=Q(beneficiary_user__isnull=False, status__in=['PENDING', 'ACTIVE']), fields=('will', 'beneficiary_user'), name='unique_active_or_pending_beneficiary_user_per_will'),
                ],
            },
        ),
        migrations.CreateModel(
            name='BeneficiaryInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_email', models.EmailField(db_index=True, max_length=254)),
                ('token_hash', models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('ACCEPTED', 'Accepted'), ('DECLINED', 'Declined'), ('REVOKED', 'Revoked'), ('EXPIRED', 'Expired')], db_index=True, default='PENDING', max_length=32)),
                ('expires_at', models.DateTimeField()),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('inviter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sent_beneficiary_invitations', to=settings.AUTH_USER_MODEL)),
                ('relationship', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='beneficiaries.willbeneficiary')),
            ],
            options={
                'ordering': ('-created_at',),
                'indexes': [
                    models.Index(fields=['recipient_email', 'status'], name='ben_rec_status_idx'),
                    models.Index(fields=['relationship', 'status'], name='ben_rel_status_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(condition=Q(status='PENDING'), fields=('relationship',), name='unique_pending_invitation_per_relationship'),
                ],
            },
        ),
    ]
