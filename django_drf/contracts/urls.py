from django.urls import path

from .views import BatchDetailView, BatchListCreateView, DocumentDetailView, FindingReviewView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view()),
    path("batches/", BatchListCreateView.as_view()),
    path("batches/<uuid:batch_id>/", BatchDetailView.as_view()),
    path("documents/<uuid:document_id>/", DocumentDetailView.as_view()),
    path("findings/<uuid:finding_id>/review/", FindingReviewView.as_view()),
]
