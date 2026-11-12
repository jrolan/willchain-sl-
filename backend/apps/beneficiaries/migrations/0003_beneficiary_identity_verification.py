from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('beneficiaries', '0002_beneficiaryallocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='willbeneficiary',
            name='identity_verification_code_hash',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='willbeneficiary',
            name='identity_verification_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='willbeneficiary',
            name='identity_verification_method',
            field=models.CharField(blank=True, default='EMAIL_OTP', max_length=32),
        ),
        migrations.AddField(
            model_name='willbeneficiary',
            name='identity_verification_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='willbeneficiary',
            name='identity_verification_status',
            field=models.CharField(choices=[('PENDING', 'Pending verification'), ('VERIFIED', 'Verified'), ('REJECTED', 'Rejected')], db_index=True, default='PENDING', max_length=32),
        ),
        migrations.AddField(
            model_name='willbeneficiary',
            name='identity_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
