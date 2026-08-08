import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Batch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("variables", models.JSONField()),
                ("submitted_by_subject", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("partial_failed", "Partially failed"), ("failed", "Failed")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="ContractDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("original_filename", models.CharField(max_length=255)),
                ("content", models.FileField(upload_to="documents/%Y/%m/%d")),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="contracts.batch")),
            ],
        ),
        migrations.CreateModel(
            name="Finding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("variable_name", models.CharField(max_length=100)),
                ("extracted_value", models.CharField(max_length=500)),
                ("review_status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("reviewer_name", models.CharField(blank=True, max_length=100)),
                ("reviewer_subject", models.CharField(blank=True, max_length=255)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="findings", to="contracts.contractdocument")),
            ],
        ),
        migrations.AddConstraint(model_name="finding", constraint=models.UniqueConstraint(fields=("document", "variable_name"), name="one_finding_per_variable")),
    ]
