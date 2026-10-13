from rest_framework import serializers

from .models import DocumentIntegrityCheck, WillDocument


class WillDocumentSerializer(serializers.ModelSerializer):
    replaced_from_id = serializers.IntegerField(read_only=True)
    replaced_by_id = serializers.IntegerField(read_only=True)
    latest_integrity_check = serializers.SerializerMethodField()

    class Meta:
        model = WillDocument
        fields = (
            'id', 'document_type', 'description', 'original_filename', 'media_type',
            'file_size', 'checksum_sha256', 'status', 'version', 'created_at',
            'updated_at', 'deleted_at', 'replaced_from_id', 'replaced_by_id', 'latest_integrity_check',
        )
        read_only_fields = fields

    def get_latest_integrity_check(self, obj):
        check = obj.integrity_checks.first()
        return DocumentIntegrityCheckSerializer(check).data if check else None


class DocumentMetadataUpdateSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=WillDocument.DocumentType.choices, required=False)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Provide at least one permitted metadata field.')
        return attrs


class DocumentIntegrityCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentIntegrityCheck
        fields = ('id', 'result', 'expected_checksum', 'computed_checksum', 'error_code', 'created_at')
        read_only_fields = fields


class AdminDocumentMetadataSerializer(serializers.ModelSerializer):
    will_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = WillDocument
        fields = ('id', 'will_id', 'document_type', 'media_type', 'file_size', 'status', 'version', 'created_at')
        read_only_fields = fields