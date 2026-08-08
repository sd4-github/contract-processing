import zipfile
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import record_event
from .models import Batch, ContractDocument, Finding
from .permissions import CanReview, CanSubmit, CanView
from .serializers import BatchSerializer, BatchUploadSerializer, DocumentSerializer, FindingSerializer, HealthSerializer, ReviewSerializer
from .tasks import extract_document

MAX_DOCUMENTS = 1_000
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}


def queue_documents(batch_id, document_ids):
    """Publish and audit each task only after its batch transaction commits."""
    for document_id in document_ids:
        extract_document.delay(document_id)
        record_event("document_queued", batch_id=str(batch_id), document_id=str(document_id))


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(tags=["System"], responses=HealthSerializer, auth=[])
    def get(self, request):
        return Response({"status": "ok"})


class BatchListCreateView(APIView):
    permission_classes = [CanSubmit]

    @extend_schema(
        tags=["Batches"],
        request=BatchUploadSerializer,
        responses={202: BatchSerializer},
        description="Upload a ZIP (1–1,000 PDF, DOC, DOCX, or TXT files) and a JSON array of variables. One Celery task is queued per document.",
        examples=[OpenApiExample("Rent agreement fields", value={"variables": '["security_deposit", "monthly_rent", "notice_period"]'}, request_only=True)],
    )
    def post(self, request):
        serializer = BatchUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        upload = serializer.validated_data["zip_file"]
        try:
            # Inspect metadata before creating database rows to reject oversized or malformed batches atomically.
            archive = zipfile.ZipFile(upload)
            members = [member for member in archive.infolist() if not member.is_dir()]
        except zipfile.BadZipFile:
            return Response({"zip_file": ["Invalid ZIP archive."]}, status=status.HTTP_400_BAD_REQUEST)

        if not members or len(members) > MAX_DOCUMENTS:
            return Response({"zip_file": [f"Archive must contain between 1 and {MAX_DOCUMENTS} documents."]}, status=status.HTTP_400_BAD_REQUEST)
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or "\\" in member.filename or ".." in path.parts:
                return Response({"zip_file": ["Archive contains an unsafe path."]}, status=status.HTTP_400_BAD_REQUEST)
            if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                return Response({"zip_file": [f"Unsupported document type: {path.suffix or '(none)'}."]}, status=status.HTTP_400_BAD_REQUEST)
            if member.file_size > MAX_DOCUMENT_BYTES:
                return Response({"zip_file": [f"{path.name} exceeds the 15 MB document limit."]}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            batch = Batch.objects.create(
                variables=serializer.validated_data["variables"],
                submitted_by_subject=getattr(request.user, "id", "") or "",
            )
            document_ids = []
            # Read ZIP entries directly instead of extracting them, preventing path traversal writes.
            for member in members:
                document = ContractDocument.objects.create(
                    batch=batch,
                    original_filename=PurePosixPath(member.filename).name,
                    size_bytes=member.file_size,
                    content=ContentFile(archive.read(member), name=PurePosixPath(member.filename).name),
                )
                document_ids.append(str(document.id))
            # Publishing after commit prevents workers from observing document IDs that a failed transaction removed.
            transaction.on_commit(
                lambda ids=tuple(document_ids), batch_id=str(batch.id): queue_documents(batch_id, ids)
            )

        archive.close()
        record_event("batch_created", batch_id=str(batch.id), document_count=len(document_ids), variables=batch.variables)
        return Response(BatchSerializer(batch).data, status=status.HTTP_202_ACCEPTED)


class BatchDetailView(APIView):
    permission_classes = [CanView]

    @extend_schema(tags=["Batches"], responses=BatchSerializer, description="Return the aggregate batch status, documents, findings, and review state.")
    def get(self, request, batch_id):
        batch = Batch.objects.prefetch_related("documents__findings").filter(id=batch_id).first()
        if not batch:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(BatchSerializer(batch).data)


class DocumentDetailView(APIView):
    permission_classes = [CanView]

    @extend_schema(tags=["Documents"], responses=DocumentSerializer)
    def get(self, request, document_id):
        document = ContractDocument.objects.prefetch_related("findings").filter(id=document_id).first()
        if not document:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DocumentSerializer(document).data)


class FindingReviewView(APIView):
    permission_classes = [CanReview]

    @extend_schema(
        tags=["Findings"],
        request=ReviewSerializer,
        responses=FindingSerializer,
        description="Accept or reject one extracted finding. Requires the `reviewer` or `administrator` Keycloak role.",
    )
    def patch(self, request, finding_id):
        serializer = ReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        # Lock prevents two reviewers from silently overwriting each other's decision mid-request.
        with transaction.atomic():
            finding = Finding.objects.select_for_update().filter(id=finding_id).first()
            if not finding:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            finding.review_status = serializer.validated_data["decision"]
            # The display name is provided for local demos; production identity is persisted from the verified subject.
            finding.reviewer_name = serializer.validated_data["reviewer_name"]
            finding.reviewer_subject = getattr(request.user, "id", "") or ""
            finding.reviewed_at = timezone.now()
            finding.save(update_fields=["review_status", "reviewer_name", "reviewer_subject", "reviewed_at"])
        record_event("finding_reviewed", finding_id=str(finding.id), decision=finding.review_status, reviewer_name=finding.reviewer_name)
        return Response(FindingSerializer(finding).data)
