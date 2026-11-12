from rest_framework import serializers

from .models import DocumentIntegrityRecord, WillIntegrityRecord, WillIntegrityVerification


class WillIntegrityVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WillIntegrityVerification
        fields = (
            'result',
            'content_matches',
            'chain_matches',
            'details',
            'checked_at',
        )
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get('hide_documents'):
            data['details'] = {'error_code': data['details'].get('error_code', '')}
        return data


class DocumentIntegrityStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentIntegrityRecord
        fields = (
            'document_id',
            'document_version',
            'record_reference',
            'network',
            'chain_id',
            'contract_address',
            'anchor_status',
            'transaction_hash',
            'block_number',
            'confirmations',
            'last_error_code',
            'confirmed_at',
        )
        read_only_fields = fields


class WillIntegrityStatusSerializer(serializers.ModelSerializer):
    latest_verification = serializers.SerializerMethodField()
    document_records = serializers.SerializerMethodField()

    class Meta:
        model = WillIntegrityRecord
        fields = (
            'record_reference',
            'finalized_version',
            'network',
            'chain_id',
            'contract_address',
            'anchor_status',
            'transaction_hash',
            'block_number',
            'confirmations',
            'last_error_code',
            'submitted_at',
            'confirmed_at',
            'latest_verification',
            'document_records',
        )
        read_only_fields = fields

    def get_latest_verification(self, obj):
        check = obj.verifications.first()
        return (
            WillIntegrityVerificationSerializer(
                check,
                context={'hide_documents': self.context.get('hide_documents', False)},
            ).data
            if check
            else None
        )

    def get_document_records(self, obj):
        if self.context.get('hide_documents'):
            return []
        records = obj.document_records.all()
        return DocumentIntegrityStatusSerializer(records, many=True).data


class IntegrityOperationsWillSerializer(serializers.ModelSerializer):
    will_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = WillIntegrityRecord
        fields = (
            'will_id',
            'record_reference',
            'network',
            'chain_id',
            'contract_address',
            'anchor_status',
            'transaction_hash',
            'block_number',
            'confirmations',
            'attempts',
            'last_error_code',
            'updated_at',
        )
        read_only_fields = fields


class IntegrityOperationsDocumentSerializer(serializers.ModelSerializer):
    will_id = serializers.IntegerField(source='will_record.will_id', read_only=True)
    document_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = DocumentIntegrityRecord
        fields = (
            'will_id',
            'document_id',
            'record_reference',
            'network',
            'chain_id',
            'contract_address',
            'anchor_status',
            'transaction_hash',
            'block_number',
            'confirmations',
            'attempts',
            'last_error_code',
            'updated_at',
        )
        read_only_fields = fields
