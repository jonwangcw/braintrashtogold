from app.processing.ocr import OCRSnippet
from app.processing.transcript_reconcile import reconcile_transcript_with_ocr


def test_reconcile_transcript_prefers_slide_confirmed_term():
    transcript = "Today we cover Kubernets deployment basics and service meshes."
    ocr_snippets = [
        OCRSnippet(timestamp_seconds=15, text="Kubernetes Architecture", confidence=0.91, frame_path="f1.jpg"),
        OCRSnippet(timestamp_seconds=30, text="Kubernetes Cluster Service", confidence=0.88, frame_path="f2.jpg"),
    ]

    result = reconcile_transcript_with_ocr(transcript, ocr_snippets)

    assert "Kubernetes deployment basics" in result.corrected_transcript
    assert result.corrections
    assert result.corrections[0].original == "Kubernets"
    assert result.corrections[0].corrected == "Kubernetes"


def test_reconcile_transcript_no_regression_with_sparse_ocr():
    transcript = "We compare Postgres and SQLite query planners."
    ocr_snippets = [
        OCRSnippet(timestamp_seconds=15, text="PostgreSQL", confidence=0.49, frame_path="f1.jpg"),
    ]

    result = reconcile_transcript_with_ocr(transcript, ocr_snippets)

    assert result.corrected_transcript == transcript
    assert result.corrections == []
