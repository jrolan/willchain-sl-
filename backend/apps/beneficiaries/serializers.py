from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.wills.models import Will
from .models import BeneficiaryInvitation, WillBeneficiary


class WillBeneficiarySerializer(serializers.ModelSerializer):
    recipient_email = serializers.SerializerMethodField()
    beneficiary_user_email = serializers.SerializerMethodField()
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
            'latest_invitation_status',
            'latest_invitation_expires_at',
            'latest_invitation_sent_at',
            'full_name',
            'relationship_type',
            'status',
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
            raise serializers.ValidationError({'will': 'Only DRAFT wills can accept beneficiary invitations.'})
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
        request = self.context['request']
        will = validated_data.pop('will')
        email = validated_data.pop('recipient_email')
        relationship = WillBeneficiary.objects.create(
            will=will,
            normalized_email=email,
            full_name=validated_data.get('full_name', ''),
            relationship_type=validated_data.get('relationship_type', WillBeneficiary.RelationshipType.PRIMARY),
            status=WillBeneficiary.Status.PENDING,
        )
        raw_token = BeneficiaryInvitation.generate_token()
        invitation = BeneficiaryInvitation.objects.create(
            relationship=relationship,
            inviter=request.user,
            recipient_email=email,
            status=BeneficiaryInvitation.Status.PENDING,
            expires_at=timezone.now() + timedelta(days=7),
            token_hash=BeneficiaryInvitation.hash_token(raw_token),
        )
        self.context['raw_invitation_token'] = raw_token
        return relationship


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
        fields = ('id', 'recipient_email', 'full_name', 'relationship_type', 'status', 'accepted_at', 'created_at')
        read_only_fields = fields
