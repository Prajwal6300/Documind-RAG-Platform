"""Deterministic safety checks for the final answer and SSE response paths."""

from unittest.mock import patch

from backend.src.pipeline import rag_pipeline
from backend.src.prompts import NO_CONTEXT_MESSAGE
from backend.src.analysis import document_analyzer


def _candidate(text="The leave policy allows 15 days of annual leave."):
    return {
        "chunk_id": "chunk-1",
        "text": text,
        "distance": 0.2,
        "_score": 0.9,
        "rerank_score": 0.9,
        "final_score": 0.9,
        "keyword_ratio": 0.9,
        "metadata": {"document_id": "policy-doc", "source": "policy.pdf", "page": 1},
    }


def _pipeline_patches(answer):
    candidate = _candidate()
    return (
        patch.object(rag_pipeline, "retrieve", return_value=[candidate]),
        patch.object(rag_pipeline, "rerank_chunks", return_value=[candidate]),
        patch.object(rag_pipeline, "generate_answer", return_value=answer),
    )


def test_grounded_answer_is_returned_with_its_single_real_citation():
    patches = _pipeline_patches("The policy allows 15 days of annual leave.")
    with patches[0], patches[1], patches[2]:
        result = rag_pipeline.answer_question("How many annual leave days are allowed?", document_id="policy-doc")

    assert result["no_context"] is False
    assert result["groundedness"]["score"] >= 0.55
    assert [source["source"] for source in result["sources"]] == ["policy.pdf"]
    assert len(result["evidences"]) == 1


def test_low_groundedness_always_refuses_even_when_sufficiency_passes():
    patches = _pipeline_patches("The chief executive's private phone number is 555-0100.")
    low_score = {
        "score": 0.15,
        "confidence": "Low",
        "is_grounded": False,
        "term_overlap": 0.0,
        "avg_retrieval": 0.9,
    }
    with patches[0], patches[1], patches[2], patch.object(rag_pipeline, "calculate_groundedness_score", return_value=low_score):
        result = rag_pipeline.answer_question("What is the CEO phone number?", document_id="policy-doc")

    assert result["answer"] == NO_CONTEXT_MESSAGE
    assert result["no_context"] is True
    assert result["sources"] == []
    assert result["groundedness"]["score"] == 0.15


def test_stream_never_emits_an_unvalidated_answer_before_refusal():
    patches = _pipeline_patches("An unrelated confident answer.")
    low_score = {"score": 0.15, "confidence": "Low", "is_grounded": False}
    with patches[0], patches[1], patches[2], patch.object(rag_pipeline, "calculate_groundedness_score", return_value=low_score):
        events = list(rag_pipeline.answer_question_stream("Ask an unsupported question", document_id="policy-doc"))

    emitted_text = "".join(event.get("token", "") for event in events)
    metadata = next(event for event in events if event["type"] == "metadata")
    assert emitted_text == NO_CONTEXT_MESSAGE
    assert metadata["no_context"] is True
    assert metadata["sources"] == []


def test_scoped_question_is_retrieved_only_from_the_selected_document():
    candidate = _candidate("Certificate issued to Mira Shah with ID CERT-239955.")
    with patch.object(rag_pipeline, "retrieve", return_value=[candidate]) as retrieve, patch.object(rag_pipeline, "rerank_chunks", return_value=[candidate]), patch.object(rag_pipeline, "generate_answer", return_value="Certificate ID CERT-239955."), patch.object(rag_pipeline, "calculate_groundedness_score", return_value={"score": 0.9, "confidence": "High", "is_grounded": True}):
        result = rag_pipeline.answer_question("What certificate ID is shown?", document_id="certificate-doc")

    assert retrieve.call_args.kwargs["document_id"] == "certificate-doc"
    assert result["no_context"] is False


def test_analysis_discards_fabricated_summary_terms(monkeypatch):
    class Response:
        text = '{"summary": "The document approves a lunar mining project.", "document_type": "policy", "entities": [{"type": "person", "value": "Mira Shah"}]}'

    class Models:
        @staticmethod
        def generate_content(**_kwargs):
            return Response()

    class Client:
        models = Models()

    monkeypatch.setattr(document_analyzer, "get_gemini_client", lambda: Client())
    result = document_analyzer.analyze_document_text(
        [{"page": 1, "text": "Employee Mira Shah may take 15 days of annual leave. The policy describes annual leave approval, carryover, manager review, and the documented request process for employees."}],
        "misleading-name.pdf",
        is_low_text=False,
    )

    assert result["analysis_status"] == "failed"
    assert result["summary"] == ""
    assert "lunar" in " ".join(result["analysis_warnings"]).lower()


def test_typo_and_casual_query_normalizes_and_returns_grounded_answer():
    """Ensure casual phrasing and typos ('wat is the sick leave policy') return grounded answer."""
    candidate = _candidate("Employees are entitled to 12 days of casual leave and 15 days of sick leave per calendar year.")
    patches = (
        patch.object(rag_pipeline, "retrieve", return_value=[candidate]),
        patch.object(rag_pipeline, "rerank_chunks", return_value=[candidate]),
        patch.object(rag_pipeline, "generate_answer", return_value="Employees receive 15 days of sick leave per calendar year."),
    )
    with patches[0] as mock_retrieve, patches[1], patches[2]:
        result = rag_pipeline.answer_question("wat is the sick leave policy???", document_id="policy-doc")

    assert result["no_context"] is False
    assert result["groundedness"]["score"] >= 0.55
    assert len(result["sources"]) == 1
    # Check that retrieve was invoked with normalized keywords / resolved query
    assert mock_retrieve.call_count == 1
    call_kwargs = mock_retrieve.call_args.kwargs
    assert "sick" in call_kwargs.get("query_keywords", []) or "leave" in call_kwargs.get("query_keywords", [])


def test_vague_scoped_query_resolves_and_returns_grounded_answer():
    """Ensure vague queries ('what is it?') scoped to a document resolve using scope context."""
    candidate = _candidate("The Employee Conduct Policy outlines standards for professional behavior, attendance, and remote work.")
    patches = (
        patch.object(rag_pipeline, "retrieve", return_value=[candidate]),
        patch.object(rag_pipeline, "rerank_chunks", return_value=[candidate]),
        patch.object(rag_pipeline, "generate_answer", return_value="This document outlines standards for professional behavior and attendance."),
    )
    with patches[0] as mock_retrieve, patches[1], patches[2]:
        result = rag_pipeline.answer_question("what is it?", document_id="policy-doc")

    assert result["no_context"] is False
    assert result["groundedness"]["score"] >= 0.55
    assert len(result["sources"]) == 1

