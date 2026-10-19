"""
Serializers for Module 5: Verification & Legal Workflow.

Protects against will-content and title exposure:
  - `will` is exposed solely as a PrimaryKeyRelatedField (ID only).
  - `storage_key` is strictly excluded from all serializers.
  - `AssignedLawyerPublicSerializer` is a plain `Serializer` exposing only `display_name` and `assigned_at`.
  - `Module8StatusSerializer` is a plain read-only boundary serializer exposing only 5 minimal fields.
"""

from rest_framework import serializers

from apps.accounts.models import User
from apps.wills.models import Will

from .models import (
    CaseEvidence,
    CaseStatusHistory,
    EligibilityAssessment,
    VerificationCase,
    WillDisclosureAuthorization,
)


class AssignedLawyerPublicSerializer(serializers.Serializer):
    """
    Plain DRF Serializer (NOT a ModelSerializer) to prevent accidental field leakage.
    Exposes only display_name and assigned_at.
    """
    display_name = serializers.SerializerMethodField()
    assigned_at = serializers.DateTimeField(read_only=True)

    def get_display_name(self, obj):
        if not obj:
            return None
        # obj is a User instance
        full_name = f'{obj.first_name} {obj.last_name}'.strip()
        return full_name or 'Assigned Legal Verifier'


class CaseStatusHistorySerializer(serializers.ModelSerializer):
    """Read-only serializer for append-only case status timeline."""
    actor_role = serializers.SerializerMethodField()

    class Meta:
        model = CaseStatusHistory
        fields = (
            'id',
            'from_status',
            'to_status',
            'actor_role',
            'notes',
            'created_at',
        )
        read_only_fields = fields

    def get_actor_role(self, obj):
        if obj.actor:
            return obj.actor.role
        return None


class CaseEvidenceSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for CaseEvidence metadata.
    storage_key is NEVER included here.
    """
    class Meta:
        model = CaseEvidence
        fields = (
            'id',
            'evidence_type',
            'description',
            'original_filename',
            'media_type',
            'file_size',
            'checksum_sha256',
            'sufficiency_flag',
            'created_at',
        )
        read_only_fields = fields


class WillDisclosureAuthorizationSerializer(serializers.ModelSerializer):
    """Read-only metadata for pre-death will copy disclosure."""
    class Meta:
        model = WillDisclosureAuthorization
        fields = (
            'id',
            'original_filename',
            'media_type',
            'file_size',
            'checksum_sha256',
            'is_active',
            'revoked_at',
            'created_at',
        )
        read_only_fields = fields


class EligibilityAssessmentSerializer(serializers.ModelSerializer):
    """Read-only assessment representation."""
    assessed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EligibilityAssessment
        fields = (
            'id',
            'is_eligible',
            'notes',
            'assessed_at',
            'assessed_by_name',
        )
        read_only_fields = fields

    def get_assessed_by_name(self, obj):
        if obj.assessed_by:
            return f'{obj.assessed_by.first_name} {obj.assessed_by.last_name}'.strip()
        return None


class VerificationCaseSerializer(serializers.ModelSerializer):
    """
    Read-only detailed case serializer.
    Protects privacy:
      - `will` is primary key only (no title, no content).
      - `assigned_lawyer_display` uses AssignedLawyerPublicSerializer.
      - nested evidence, status_history, disclosure_authorization, eligibility_assessment.
    """
    will = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_lawyer_display = serializers.SerializerMethodField()
    evidence = CaseEvidenceSerializer(many=True, read_only=True)
    status_history = CaseStatusHistorySerializer(many=True, read_only=True)
    disclosure_authorization = WillDisclosureAuthorizationSerializer(read_only=True)
    eligibility_assessment = EligibilityAssessmentSerializer(read_only=True)

    class Meta:
        model = VerificationCase
        fields = (
            'id',
            'will',
            'case_type',
            'submission_type',
            'status',
            'claimed_executor_basis',
            'decision_notes',
            'information_request_notes',
            'assigned_lawyer_display',
            'evidence',
            'status_history',
            'disclosure_authorization',
            'eligibility_assessment',
            'linked_prior_case',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_assigned_lawyer_display(self, obj):
        if not obj.assigned_lawyer:
            return None
        serializer = AssignedLawyerPublicSerializer(
            instance=obj.assigned_lawyer,
            context={'assigned_at': obj.assigned_at},
        )
        data = serializer.data
        data['assigned_at'] = obj.assigned_at
        return data


class VerificationCaseCreateSerializer(serializers.Serializer):
    """Input serializer for initiating a new verification case."""
    will = serializers.PrimaryKeyRelatedField(
        queryset=Will.objects.all(),
        required=False,
        allow_null=True,
    )
    case_type = serializers.ChoiceField(choices=VerificationCase.CaseType.choices)
    submission_type = serializers.ChoiceField(choices=VerificationCase.SubmissionType.choices)
    claimed_executor_basis = serializers.CharField(
        max_length=512,
        required=False,
        allow_blank=True,
        default='',
    )
    linked_prior_case = serializers.PrimaryKeyRelatedField(
        queryset=VerificationCase.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        case_type = attrs.get('case_type')
        submission_type = attrs.get('submission_type')
        will = attrs.get('will')

        if submission_type == VerificationCase.SubmissionType.OWNER_INITIATED:
            if not will:
                raise serializers.ValidationError({'will': 'A finalized will is required for pre-death review.'})
            if case_type != VerificationCase.CaseType.PRE_DEATH_REVIEW:
                raise serializers.ValidationError({'case_type': 'Owner-initiated case must be PRE_DEATH_REVIEW.'})

        elif submission_type == VerificationCase.SubmissionType.BENEFICIARY_CLAIM:
            if not will:
                raise serializers.ValidationError({'will': 'A finalized will is required for beneficiary claims.'})
            if case_type != VerificationCase.CaseType.POST_DEATH_VERIFY:
                raise serializers.ValidationError({'case_type': 'Beneficiary claim must be POST_DEATH_VERIFY.'})

        elif submission_type == VerificationCase.SubmissionType.CLAIMED_EXECUTOR:
            if case_type != VerificationCase.CaseType.POST_DEATH_VERIFY:
                raise serializers.ValidationError({'case_type': 'Claimed executor case must be POST_DEATH_VERIFY.'})

        return attrs


class EvidenceUploadSerializer(serializers.Serializer):
    """Input serializer for evidence upload."""
    evidence_type = serializers.ChoiceField(choices=CaseEvidence.EvidenceType.choices)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    file = serializers.FileField(required=True)


class DecisionSerializer(serializers.Serializer):
    """Input serializer for lawyer decision recording."""
    decision = serializers.ChoiceField(choices=[
        VerificationCase.Status.APPROVED,
        VerificationCase.Status.REJECTED,
    ])
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class InformationRequestSerializer(serializers.Serializer):
    """Input serializer for requesting additional info from claimant."""
    notes = serializers.CharField(required=True, allow_blank=False)


class EligibilityAssessmentInputSerializer(serializers.Serializer):
    """Input serializer for assessing claimed executor eligibility."""
    is_eligible = serializers.BooleanField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class LawyerAssignmentSerializer(serializers.Serializer):
    """Input serializer for assigning a lawyer to a case."""
    lawyer_id = serializers.IntegerField(required=True)


class Module8StatusSerializer(serializers.Serializer):
    """
    Read-only status representation for Module 8 boundary.
    Strictly exposes only 5 fields:
      case_id, will_id, case_type, status, approved_at.
    """
    case_id = serializers.IntegerField()
    will_id = serializers.IntegerField()
    case_type = serializers.CharField()
    status = serializers.CharField()
    approved_at = serializers.DateTimeField(allow_null=True)
