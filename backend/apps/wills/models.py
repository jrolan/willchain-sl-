from django.conf import settings
from django.db import models
from django.utils import timezone


class Will(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        FINALIZED = 'FINALIZED', 'Finalized'
        ARCHIVED = 'ARCHIVED', 'Archived'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wills',
    )
    title = models.CharField(max_length=200)
    content = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.owner.email})'

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    def finalize(self):
        if self.status != self.Status.DRAFT:
            raise ValueError('Only draft wills can be finalized.')
        self.status = self.Status.FINALIZED
        self.finalized_at = timezone.now()
        self.version += 1
        self.save(update_fields=['status', 'finalized_at', 'version', 'updated_at'])
