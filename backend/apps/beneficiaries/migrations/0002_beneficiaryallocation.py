import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_user_google_sub'),
        ('beneficiaries', '0001_initial'),
        ('verification', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BeneficiaryAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allocation_type', models.CharField(choices=[('FIXED_AMOUNT', 'Fixed amount'), ('PERCENTAGE', 'Percentage'), ('SPECIFIC_ITEM', 'Specific item')], max_length=32)),
                ('description', models.CharField(blank=True, max_length=500)),
                ('amount', models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ('currency_code', models.CharField(blank=True, max_length=3)),
                ('percentage', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('review_status', models.CharField(choices=[('PENDING', 'Pending review'), ('VERIFIED', 'Verified'), ('WITHHELD', 'Withheld')], db_index=True, default='PENDING', max_length=16)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('beneficiary', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allocations', to='beneficiaries.willbeneficiary')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_beneficiary_allocations', to=settings.AUTH_USER_MODEL)),
                ('reviewed_case', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_beneficiary_allocations', to='verification.verificationcase')),
            ],
            options={
                'ordering': ('created_at',),
                'indexes': [models.Index(fields=['beneficiary', 'review_status'], name='alloc_ben_review_idx')],
                'constraints': [
                    models.CheckConstraint(
                        condition=(
                            Q(allocation_type='FIXED_AMOUNT', amount__isnull=False, amount__gte=0, percentage__isnull=True)
                            & ~Q(currency_code='')
                            | ~Q(allocation_type='FIXED_AMOUNT')
                        ),
                        name='allocation_fixed_amount_fields',
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(allocation_type='PERCENTAGE', percentage__isnull=False, percentage__gte=0, percentage__lte=100, amount__isnull=True, currency_code='')
                            | ~Q(allocation_type='PERCENTAGE')
                        ),
                        name='allocation_percentage_fields',
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(allocation_type='SPECIFIC_ITEM', description__gt='', amount__isnull=True, percentage__isnull=True, currency_code='')
                            | ~Q(allocation_type='SPECIFIC_ITEM')
                        ),
                        name='allocation_specific_item_fields',
                    ),
                ],
            },
        ),
    ]