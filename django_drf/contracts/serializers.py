import json

from rest_framework import serializers

from .models import Batch, ContractDocument, Finding


class BatchUploadSerializer(serializers.Serializer):
    zip_file = serializers.FileField()
    variables = serializers.CharField()

    def validate_zip_file(self, value):
        if not value.name.lower().endswith(".zip"):
            raise serializers.ValidationError("zip_file must be a .zip archive.")
        return value

    def validate_variables(self, value):
        # Multipart form data carries the variable list as JSON, keeping file upload clients framework-agnostic.
        try:
            variables = json.loads(value)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError("variables must be a JSON array of strings.") from exc
        if not isinstance(variables, list) or not variables or not all(isinstance(item, str) and item.strip() for item in variables):
            raise serializers.ValidationError("variables must be a non-empty JSON array of strings.")
        normalized = [item.strip() for item in variables]
        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError("variables must not contain duplicates.")
        return normalized


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = ["id", "variable_name", "extracted_value", "review_status", "reviewer_name", "reviewer_subject", "reviewed_at", "created_at"]


class DocumentSerializer(serializers.ModelSerializer):
    findings = FindingSerializer(many=True, read_only=True)

    class Meta:
        model = ContractDocument
        fields = ["id", "original_filename", "size_bytes", "status", "error_message", "created_at", "processed_at", "findings"]


class BatchSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Batch
        fields = ["id", "variables", "submitted_by_subject", "status", "created_at", "completed_at", "documents"]


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[Finding.ReviewStatus.ACCEPTED, Finding.ReviewStatus.REJECTED])
    reviewer_name = serializers.CharField(max_length=100)


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
