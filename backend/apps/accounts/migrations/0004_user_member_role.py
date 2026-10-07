from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_account_status_alter_user_avatar_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('OWNER', 'Will Owner'),
                    ('MEMBER', 'Member'),
                    ('WITNESS', 'Witness'),
                    ('BENEFICIARY', 'Beneficiary'),
                    ('LAWYER_VERIFIER', 'Lawyer/Authorized Verifier'),
                    ('ADMINISTRATOR', 'System Administrator'),
                ],
                db_index=True,
                default='OWNER',
                max_length=32,
            ),
        ),
    ]