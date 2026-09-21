from rest_framework import serializers

from .models import Will


class WillSerializer(serializers.ModelSerializer):
    owner_email = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Will
        fields = (
            'id',
            'owner',
            'owner_email',
            'title',
            'content',
            'status',
            'version',
            'finalized_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'owner',
            'owner_email',
            'status',
            'version',
            'finalized_at',
            'created_at',
            'updated_at',
        )

    def get_owner_email(self, obj):
        return obj.owner.email

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Title is required.')
        return value.strip()

    def validate_content(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('Content must be a JSON object.')

        object_fields = ('testator', 'family', 'executor')
        for field_name in object_fields:
            field_value = value.get(field_name)
            if field_value is not None and not isinstance(field_value, dict):
                raise serializers.ValidationError({field_name: 'This section must be an object.'})

        list_fields = ('guardians', 'beneficiaries', 'gifts')
        for field_name in list_fields:
            field_value = value.get(field_name)
            if field_value is not None and (
                not isinstance(field_value, list)
                or any(not isinstance(item, dict) for item in field_value)
            ):
                raise serializers.ValidationError({field_name: 'This section must be a list of objects.'})

        text_fields = ('residual_estate', 'funeral_wishes', 'digital_assets_notes', 'review_notes')
        for field_name in text_fields:
            field_value = value.get(field_name)
            if field_value is not None and not isinstance(field_value, str):
                raise serializers.ValidationError({field_name: 'This section must be text.'})
        return value

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        if instance and instance.status == Will.Status.FINALIZED:
            raise serializers.ValidationError('This will is finalized and cannot be edited.')
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['owner'] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.version += 1
        instance.save(update_fields=['version', 'updated_at'])
        return instance
