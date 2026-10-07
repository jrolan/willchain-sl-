import hashlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def hash_existing_invitation_tokens(apps, schema_editor):
    Invitation = apps.get_model('accounts', 'Invitation')
    for invitation in Invitation.objects.all().iterator():
        if invitation.status == 'PENDING' and invitation.token_hash:
            invitation.token_hash = hashlib.sha256(invitation.token_hash.encode('utf-8')).hexdigest()
        else:
            invitation.token_hash = None
        invitation.save(update_fields=['token_hash'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_user_member_role'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='invitation',
            name='accounts_in_token_a8bcde_idx',
        ),
        migrations.RenameField(
            model_name='invitation',
            old_name='token',
            new_name='token_hash',
        ),
        migrations.RunPython(hash_existing_invitation_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='invitation',
            name='token_hash',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='invitation',
            name='accepted_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accepted_invitations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name='invitation',
            index=models.Index(fields=['token_hash', 'status'], name='accounts_in_token_a8bcde_idx'),
        ),
    ]
