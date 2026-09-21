from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('wills', '0001_initial'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='will',
            new_name='wills_will_owner_i_744445_idx',
            old_name='wills_will_owner__5bc9e9_idx',
        ),
    ]