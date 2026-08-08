import uuid

from django.db import models


class Batch(models.Model):
    # Batch status is an aggregate derived from its documents, not an independently trusted counter.
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        PARTIAL_FAILED = "partial_failed", "Partially failed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variables = models.JSONField()
    submitted_by_subject = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class ContractDocument(models.Model):
    # File bytes are abstracted by Django storage, so local media and Azure Blob Storage use one field.
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="documents")
    original_filename = models.CharField(max_length=255)
    content = models.FileField(upload_to="documents/%Y/%m/%d")
    size_bytes = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class Finding(models.Model):
    # Review status is separate from extraction status: a completed extraction may still need human review.
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(ContractDocument, on_delete=models.CASCADE, related_name="findings")
    variable_name = models.CharField(max_length=100)
    extracted_value = models.CharField(max_length=500)
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reviewer_name = models.CharField(max_length=100, blank=True)
    reviewer_subject = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # This database constraint makes redelivered Celery tasks safe to retry without duplicate findings.
        constraints = [models.UniqueConstraint(fields=["document", "variable_name"], name="one_finding_per_variable")]
