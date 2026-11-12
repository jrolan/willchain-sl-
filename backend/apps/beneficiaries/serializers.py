from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.wills.models import Will
from .models import BeneficiaryAllocation, BeneficiaryInvitation, WillBeneficiary


class BeneficiaryUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'avatar')
        read_only_fields = fields


class WillBeneficiarySerializer(serializers.ModelSerializer):
    recipient_email = serializers.SerializerMethodField()
    beneficiary_user_email = serializers.SerializerMethodField()
    beneficiary_user_profile = BeneficiaryUserProfileSerializer(source='beneficiary_user', read_only=True)
    latest_invitation_status = serializers.SerializerMethodField()
    latest_invitation_expires_at = serializers.SerializerMethodField()
    latest_invitation_sent_at = serializers.SerializerMethodField()

    class Meta:
        model = WillBeneficiary
        fields = (
            'id',
            'will',
            'recipient_email',
            'beneficiary_user',
            'beneficiary_user_email',
            'beneficiary_user_profile',
            'latest_invitation_status',
            'latest_invitation_expires_at',
            'latest_invitation_sent_at',
            'full_name',
            'relationship_type',
            'status',
            'identity_verification_status',
            'identity_verification_method',
            'identity_verified_at',
            'accepted_at',
            'revoked_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'will',
            'beneficiary_user',
            'beneficiary_user_email',
            'identity_verification_status',
            'identity_verification_method',
            'identity_verified_at',
            'accepted_at',
            'revoked_at',
            'created_at',
            'updated_at',
        )

    def get_recipient_email(self, obj):
        return obj.normalized_email

    def get_beneficiary_user_email(self, obj):
        return obj.beneficiary_user.email if obj.beneficiary_user else None

    def _latest_invitation(self, obj):
        invitations = list(obj.invitations.all())
        return invitations[0] if invitations else None

    def get_latest_invitation_status(self, obj):
        invitation = self._latest_invitation(obj)
        if invitation and invitation.status == BeneficiaryInvitation.Status.PENDING and invitation.expires_at <= timezone.now():
            return BeneficiaryInvitation.Status.EXPIRED
        return invitation.status if invitation else None

    def get_latest_invitation_expires_at(self, obj):
        invitation = self._latest_invitation(obj)
        return invitation.expires_at if invitation else None

    def get_latest_invitation_sent_at(self, obj):
        invitation = self._latest_invitation(obj)
        return invitation.sent_at if invitation else None

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        if instance and instance.will.status != Will.Status.DRAFT:
            raise serializers.ValidationError('Only DRAFT wills can be updated.')
        return attrs


class CreateWillBeneficiarySerializer(serializers.Serializer):
    recipient_email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    relationship_type = serializers.ChoiceField(choices=WillBeneficiary.RelationshipType.choices, default=WillBeneficiary.RelationshipType.PRIMARY)

    def validate_recipient_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        request = self.context['request']
        will_id = self.context['will_id']
        will = Will.objects.filter(owner=request.user, pk=will_id).first()
        if not will:
            raise serializers.ValidationError({'will': 'Will not found or not owned by the current user.'})
        if will.status != Will.Status.DRAFT:
            raise serializers.ValidationError({'will': 'Only DRAFT wills can manage beneficiary relationships.'})
        normalized_email = attrs['recipient_email'].lower()
        if WillBeneficiary.objects.filter(
            will=will,
            normalized_email=normalized_email,
            status__in=[WillBeneficiary.Status.PENDING, WillBeneficiary.Status.ACTIVE],
        ).exists():
            raise serializers.ValidationError({'recipient_email': 'This email already has a beneficiary relationship for this will.'})
        attrs['will'] = will
        return attrs

    def create(self, validated_data):
        will = validated_data.pop('will')
        email = validated_data.pop('recipient_email')
        return WillBeneficiary.objects.create(
            will=will,
            normalized_email=email,
            full_name=validated_data.get('full_name', ''),
            relationship_type=validated_data.get('relationship_type', WillBeneficiary.RelationshipType.PRIMARY),
            status=WillBeneficiary.Status.PENDING,
        )


class BeneficiaryAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BeneficiaryAllocation
        fields = (
            'id',
            'beneficiary',
            'allocation_type',
            'description',
            'amount',
            'currency_code',
            'percentage',
            'review_status',
            'reviewed_by',
            'reviewed_case',
            'reviewed_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'beneficiary',
            'review_status',
            'reviewed_by',
            'reviewed_case',
            'reviewed_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        allocation_type = attrs.get('allocation_type', getattr(instance, 'allocation_type', None))
        amount = attrs.get('amount', getattr(instance, 'amount', None))
        currency_code = attrs.get('currency_code', getattr(instance, 'currency_code', ''))
        percentage = attrs.get('percentage', getattr(instance, 'percentage', None))
        description = attrs.get('description', getattr(instance, 'description', ''))

        if allocation_type == BeneficiaryAllocation.AllocationType.FIXED_AMOUNT:
            if amount is None or amount < 0 or not currency_code or percentage is not None:
                raise serializers.ValidationError('Fixed amount allocations require a non-negative amount and currency, and cannot include a percentage.')
        elif allocation_type == BeneficiaryAllocation.AllocationType.PERCENTAGE:
            if percentage is None or not 0 <= percentage <= 100 or amount is not None or currency_code:
                raise serializers.ValidationError('Percentage allocations require a value from 0 to 100 and cannot include an amount or currency.')
        elif allocation_type == BeneficiaryAllocation.AllocationType.SPECIFIC_ITEM:
            if not description.strip() or amount is not None or percentage is not None or currency_code:
                raise serializers.ValidationError('Specific item allocations require a description and cannot include an amount or percentage.')
        return attrs


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)

    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        if not user or not user.is_authenticated:
            raise serializers.ValidationError({'token': 'Authentication is required to accept an invitation.'})
        if user.account_status != User.AccountStatus.ACTIVE or not user.email_verified:
            raise serializers.ValidationError({'token': 'Account must be active and verified.'})

        candidate_hash = BeneficiaryInvitation.hash_token(attrs['token'])
        try:
            invitation = BeneficiaryInvitation.objects.select_related('relationship__will', 'relationship__beneficiary_user').get(token_hash=candidate_hash)
        except BeneficiaryInvitation.DoesNotExist:
            raise serializers.ValidationError({'token': 'Invitation not found or token invalid.'})

        if not invitation.is_valid():
            raise serializers.ValidationError({'token': 'Invitation is expired or no longer pending.'})
        if invitation.recipient_email.lower() != user.email.lower():
            raise serializers.ValidationError({'token': 'This invitation is for a different account.'})
        if invitation.relationship.status != WillBeneficiary.Status.PENDING:
            raise serializers.ValidationError({'token': 'This relationship is no longer pending.'})
        if invitation.relationship.will.status != Will.Status.DRAFT:
            raise serializers.ValidationError({'token': 'This will is no longer editable for invitation acceptance.'})
        if not invitation.relationship.allocations.filter(
            review_status=BeneficiaryAllocation.ReviewStatus.VERIFIED,
            release_authorization__status__in=('AUTHORIZED', 'ACKNOWLEDGED'),
            release_authorization__case__case_type='POST_DEATH_VERIFY',
            release_authorization__case__status='APPROVED',
        ).exists():
            raise serializers.ValidationError({'token': 'No allocation has been authorized for release.'})

        attrs['invitation'] = invitation
        attrs['user'] = user
        return attrs


class BeneficiaryInvitationSerializer(serializers.ModelSerializer):
    relationship_id = serializers.IntegerField(source='relationship.id', read_only=True)

    class Meta:
        model = BeneficiaryInvitation
        fields = (
            'id',
            'relationship_id',
            'recipient_email',
            'status',
            'expires_at',
            'sent_at',
            'responded_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class BeneficiaryInvitationPreviewSerializer(serializers.ModelSerializer):
    recipient_email = serializers.SerializerMethodField()

    class Meta:
        model = BeneficiaryInvitation
        fields = ('recipient_email', 'status', 'expires_at')
        read_only_fields = fields

    def get_recipient_email(self, obj):
        local, separator, domain = obj.recipient_email.partition('@')
        if not separator:
            return '***'
        return f'{local[:1]}***@{domain}'


class BeneficiarySelfRelationshipSerializer(serializers.ModelSerializer):
    recipient_email = serializers.EmailField(read_only=True, source='normalized_email')

    class Meta:
        model = WillBeneficiary
        fields = (
            'id',
            'recipient_email',
            'full_name',
            'relationship_type',
            'status',
            'identity_verification_status',
            'identity_verified_at',
            'accepted_at',
            'created_at',
        )
        read_only_fields = fields


class BeneficiaryReleaseTokenSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, write_only=True, trim_whitespace=False)


class BeneficiaryReleaseIdentityVerifySerializer(BeneficiaryReleaseTokenSerializer):
    code = serializers.CharField(required=True, min_length=6, max_length=6, trim_whitespace=True)


class BeneficiaryReleaseRegistrationSerializer(BeneficiaryReleaseTokenSerializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)


class BeneficiaryAllocationAccessSerializer(serializers.ModelSerializer):
    will_title = serializers.CharField(source='beneficiary.will.title', read_only=True)
    release_status = serializers.CharField(source='release_authorization.status', read_only=True)
    released_at = serializers.DateTimeField(source='release_authorization.authorized_at', read_only=True)

    class Meta:
        model = BeneficiaryAllocation
        fields = (
            'id',
            'will_title',
            'allocation_type',
            'description',
            'amount',
            'currency_code',
            'percentage',
            'release_status',
            'released_at',
        )
        read_only_fields = fields
