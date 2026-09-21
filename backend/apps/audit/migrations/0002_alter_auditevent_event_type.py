from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('USER_REGISTERED', 'User registered'),
                    ('LOGIN_SUCCESS', 'Login successful'),
                    ('LOGIN_FAILED', 'Login failed'),
                    ('LOGOUT', 'User logged out'),
                    ('PASSWORD_CHANGED', 'Password changed'),
                    ('PASSWORD_RESET_REQUESTED', 'Password reset requested'),
                    ('PASSWORD_RESET_COMPLETED', 'Password reset completed'),
                    ('EMAIL_VERIFIED', 'Email verified'),
                    ('INVITATION_SENT', 'Invitation sent'),
                    ('INVITATION_ACCEPTED', 'Invitation accepted'),
                    ('ACCOUNT_STATUS_CHANGED', 'Account status changed'),
                    ('WILL_CREATED', 'Will created'),
                    ('WILL_ACCESSED', 'Will accessed'),
                    ('WILL_UPDATED', 'Will updated'),
                    ('WILL_FINALIZED', 'Will finalized'),
                    ('WILL_ACCESS_DENIED', 'Will access denied'),
                    ('SECURITY_ALERT', 'Security alert'),
                ],
                db_index=True,
                max_length=64,
            ),
        ),
    ]