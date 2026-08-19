"""Comprehensive Evaluation Harness for DocuMind RAG Pipeline.

Calculates real empirical metrics:
- Retrieval Precision@k
- Refusal Accuracy (Zero Hallucination on out-of-domain questions)
- Answer Correctness (Fact & Entity Keyword Verification)
- Latency (Retrieval ms, Generation ms, Total ms)
- Groundedness Score Distribution
"""

import os
import sys
import json
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rag.document_loader import load_document
from rag.chunker import create_chunks
from rag.vector_store import add_chunks, clear_all_documents, get_collection
from rag.rag_pipeline import answer_question, NO_CONTEXT_MESSAGE
import backend.database as db

DATASET_PATH = Path("scripts/eval_dataset.json")
TEST_DATA_DIR = Path("test_data")
OUTPUT_REPORT = Path("evaluation/eval_report.json")
OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)


def index_test_documents():
    """Index all test documents into vector store and SQLite."""
    print("\n[EVAL SETUP] Indexing test documents from test_data/...")
    clear_all_documents()
    
    test_files = list(TEST_DATA_DIR.glob("*.*"))
    indexed = 0

    for file_path in test_files:
        if file_path.suffix.lower() not in (".pdf", ".docx", ".txt", ".csv", ".xlsx"):
            continue

        doc_id = f"eval-doc-{file_path.stem}"
        pages = load_document(str(file_path))
        chunks = create_chunks(pages=pages, source=file_path.name, document_id=doc_id)

        if chunks:
            add_chunks(chunks)
            db.insert_document({
                "id": doc_id,
                "name": file_path.name,
                "title": file_path.stem.replace("_", " ").title(),
                "type": file_path.suffix.lstrip(".").upper(),
                "size": f"{file_path.stat().st_size / 1024:.1f} KB",
                "size_bytes": file_path.stat().st_size,
                "pages": len(pages),
                "chunks": len(chunks),
                "file_path": str(file_path),
                "status": "indexed",
            })
            indexed += 1
            print(f"  [OK] Indexed '{file_path.name}' ({len(pages)} pages, {len(chunks)} chunks)")

    print(f"[EVAL SETUP] Successfully indexed {indexed} documents ({get_collection().count()} total chunks in Chroma).\n")


def run_evaluation():
    """Execute all test items in eval_dataset.json and compute metrics."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Starting evaluation across {len(dataset)} benchmark queries...")
    print("=" * 80)

    results = []
    total_queries = len(dataset)
    answerable_count = 0
    answerable_correct = 0
    unanswerable_count = 0
    refusal_correct = 0
    retrieval_hits = 0
    latencies = []

    for idx, item in enumerate(dataset, 1):
        q_id = item["id"]
        question = item["question"]
        should_refuse = item["should_refuse"]
        expected_src = item.get("expected_source")
        expected_kw = item.get("expected_keywords", [])

        t0 = time.time()
        res = answer_question(question, stream=False, debug=True)
        elapsed_ms = (time.time() - t0) * 1000
        latencies.append(elapsed_ms)

        answer_text = res.get("intro", "") + " " + res.get("answer", "")
        no_context = res.get("no_context", False)
        sources_cited = [s.get("name") for s in res.get("sources", [])]
        groundedness_score = (res.get("groundedness") or {}).get("score", 0.0)

        # Check refusal accuracy
        is_refusal = no_context or NO_CONTEXT_MESSAGE.lower() in answer_text.lower() or "couldn't find" in answer_text.lower()

        if should_refuse:
            unanswerable_count += 1
            refused_correctly = is_refusal
            if refused_correctly:
                refusal_correct += 1
            passed = refused_correctly
            retrieval_pass = True  # Not applicable
        else:
            answerable_count += 1
            # Check retrieval hit
            retrieval_pass = any(expected_src.lower() in str(s).lower() for s in sources_cited) if expected_src else True
            if retrieval_pass:
                retrieval_hits += 1

            # Check keyword presence in answer
            kw_hits = [kw.lower() in answer_text.lower() for kw in expected_kw]
            ans_correct = all(kw_hits) and not is_refusal
            if ans_correct:
                answerable_correct += 1
            passed = ans_correct and retrieval_pass

        status_tag = "PASS" if passed else "FAIL"
        print(f"[{idx:02d}/{total_queries:02d}] [{status_tag}] | {question[:50]}... ({elapsed_ms:.0f}ms)")
        if not passed:
            print(f"    Expected refuse: {should_refuse}, Got refuse: {is_refusal}")
            print(f"    Expected src: {expected_src}, Got sources: {sources_cited}")
            print(f"    Answer: {answer_text[:120]}...")

        results.append({
            "id": q_id,
            "question": question,
            "should_refuse": should_refuse,
            "is_refusal": is_refusal,
            "expected_source": expected_src,
            "sources_cited": sources_cited,
            "passed": passed,
            "groundedness_score": groundedness_score,
            "latency_ms": round(elapsed_ms, 1),
        })

    # Compute aggregate metrics
    retrieval_precision = (retrieval_hits / answerable_count * 100) if answerable_count else 100.0
    refusal_accuracy = (refusal_correct / unanswerable_count * 100) if unanswerable_count else 100.0
    answer_correctness = (answerable_correct / answerable_count * 100) if answerable_count else 100.0
    overall_accuracy = ((answerable_correct + refusal_correct) / total_queries * 100)
    avg_latency = sum(latencies) / len(latencies)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_queries": total_queries,
        "answerable_queries": answerable_count,
        "unanswerable_queries": unanswerable_count,
        "overall_accuracy_percent": round(overall_accuracy, 1),
        "retrieval_precision_k_percent": round(retrieval_precision, 1),
        "refusal_accuracy_percent": round(refusal_accuracy, 1),
        "answer_correctness_percent": round(answer_correctness, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "min_latency_ms": round(min(latencies), 1),
        "max_latency_ms": round(max(latencies), 1),
    }

    print("\n" + "=" * 80)
    print("DOCUMIND RAG EVALUATION BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Total Benchmark Queries:     {total_queries}")
    print(f"Overall Accuracy:            {overall_accuracy:.1f}%")
    print(f"Retrieval Precision@k:       {retrieval_precision:.1f}%")
    print(f"Refusal Accuracy (Anti-Hallucination): {refusal_accuracy:.1f}%")
    print(f"Answer Correctness:          {answer_correctness:.1f}%")
    print(f"Average Response Latency:    {avg_latency:.0f} ms")
    print("=" * 80)

    # Save to file
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    print(f"\nDetailed evaluation report saved to: {OUTPUT_REPORT}")
    return summary


if __name__ == "__main__":
    index_test_documents()
    run_evaluation()
