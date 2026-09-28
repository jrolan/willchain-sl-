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
        trimmed = value.strip()
        if len(trimmed) > 200:
            raise serializers.ValidationError('Title must not exceed 200 characters.')
        return trimmed

    def _check_depth(self, data, current_depth=1, max_depth=10):
        if current_depth > max_depth:
            raise serializers.ValidationError('Content structure cannot be nested deeper than 10 levels.')
        if isinstance(data, dict):
            for v in data.values():
                self._check_depth(v, current_depth + 1, max_depth)
        elif isinstance(data, list):
            for item in data:
                self._check_depth(item, current_depth + 1, max_depth)

    def validate_content(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('Content must be a JSON object.')

        self._check_depth(value, current_depth=1, max_depth=10)

        import json
        try:
            serialized = json.dumps(value)
            if len(serialized.encode('utf-8')) > 100 * 1024:
                raise serializers.ValidationError('Content size exceeds maximum allowed limit of 100 KB.')
        except (TypeError, ValueError):
            raise serializers.ValidationError('Content must be a valid JSON object.')

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
