"""Comprehensive accuracy and retrieval test suite for the upgraded DocuMind pipeline.

Tests all 10+ core scenarios:
  1. Exact Name Retrieval & Grounding
  2. Technical Skills Retrieval
  3. Exact Employee ID / Identifier Match Boost
  4. Exact Date & Timeline Retrieval
  5. Unanswerable / Hallucination-prevention Gate (No-answer detection)
  6. Multi-document retrieval (document #2 retrieval)
  7. Multi-document synthesis retrieval (documents #1 and #3)
  8. Duplicate Document Protection
  9. Query Normalization with Varied Phrasing (same evidence for varied wording)
  10. Exact Code/Identifier Lookup (EMP1024, PO-2026-0042, etc.)
  11. Table Data Extraction & Retrieval (DOCX / PDF tables)
  12. Follow-Up Reference Resolution
"""

import hashlib
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from rag.chunker import create_chunks
from rag.document_loader import load_document
from rag.vector_store import (
    add_chunks,
    register_document,
    document_exists,
    list_documents,
    get_document,
)
from rag.retriever import retrieve, retrieve_for_summary
from rag.question_analyzer import (
    classify_question,
    extract_keywords,
    extract_entities,
    expand_query,
    resolve_follow_up,
    normalize_query_text,
)
from rag.rag_pipeline import answer_question, NO_CONTEXT_MESSAGE

TEST_DATA = "test_data"
PASS = 0
FAIL = 0
FAILURES = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} — {detail}")
        print(f"  [FAIL] {name}  {detail}")


def file_hash(content):
    return hashlib.sha256(content).hexdigest()


def index_file(path):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    labels = {"pdf": "PDF", "docx": "DOCX", "txt": "TXT"}

    with open(path, "rb") as f:
        content = f.read()

    doc_id = file_hash(content)
    if document_exists(doc_id):
        return doc_id

    pages = load_document(path)
    chunks = create_chunks(pages, name, document_id=doc_id)
    add_chunks(chunks)
    register_document(
        doc_id=doc_id,
        source=name,
        file_type=labels.get(ext, ext.upper()),
        page_count=len(pages),
        chunk_count=len(chunks),
    )
    return doc_id


def main():
    global PASS, FAIL, FAILURES

    print("=" * 60)
    print("DOCUMIND HIGH-ACCURACY RETRIEVAL TEST SUITE")
    print("=" * 60)

    # 1. Index test files
    index_file(os.path.join(TEST_DATA, "company_policy.pdf"))
    index_file(os.path.join(TEST_DATA, "employee_handbook.pdf"))
    index_file(os.path.join(TEST_DATA, "resume.txt"))
    index_file(os.path.join(TEST_DATA, "inventory.docx"))

    docs = {d["source"]: d for d in list_documents()}
    print(f"Indexed {len(docs)} documents: {list(docs.keys())}\n")

    # TEST 1: Exact Name
    print("--- TEST 1: Exact Name Retrieval ---")
    q = "What is the candidate's name?"
    res = retrieve(q, query_keywords=extract_keywords(q), entities=extract_entities(q))
    texts = " ".join(r.get("text", "") for r in res)
    check("Candidate name present in evidence", "Prajwal" in texts, f"got: {texts[:100]}")
    check("Source is resume.txt", any((r.get("metadata") or {}).get("source") == "resume.txt" for r in res))

    # TEST 2: Technical Skills
    print("\n--- TEST 2: Technical Skills Retrieval ---")
    q = "What are the technical skills?"
    res = retrieve(q, query_keywords=extract_keywords(q), entities=extract_entities(q))
    texts = " ".join(r.get("text", "") for r in res)
    check("Python skill present", "Python" in texts)
    check("React skill present", "React" in texts)
    check("SQL skill present", "SQL" in texts)

    # TEST 3: Exact Employee ID
    print("\n--- TEST 3: Exact Employee ID Retrieval ---")
    q = "What is the employee ID?"
    res = retrieve(q, query_keywords=extract_keywords(q), entities=extract_entities(q))
    texts = " ".join(r.get("text", "") for r in res)
    check("EMP1024 present in evidence", "EMP1024" in texts, f"got: {texts[:100]}")
    check("Source is company_policy.pdf", any((r.get("metadata") or {}).get("source") == "company_policy.pdf" for r in res))

    # TEST 4: Exact Joining Date
    print("\n--- TEST 4: Exact Joining Date Retrieval ---")
    q = "What is the joining date?"
    res = retrieve(q, query_keywords=extract_keywords(q), entities=extract_entities(q))
    texts = " ".join(r.get("text", "") for r in res)
    check("Joining date '15 March 2021' in evidence", "15 March 2021" in texts or ("15" in texts and "March" in texts and "2021" in texts))

    # TEST 5: Unrelated / No-Answer Question
    print("\n--- TEST 5: No-Answer Question Gate ---")
    q = "What is the CEO's favorite color?"
    r = answer_question(q, stream=False)
    check("No-answer returns not-found message", r.get("no_context") is True and (r.get("answer") == NO_CONTEXT_MESSAGE or "couldn't find" in r.get("answer", "").lower()))
    check("No sources returned for unanswerable question", len(r.get("sources") or []) == 0)

    # TEST 6: Multi-document: Document #2 Retrieval
    print("\n--- TEST 6: Document #2 Retrieval (employee_handbook.pdf) ---")
    q = "What is in the code of conduct?"
    res = retrieve(q, query_keywords=extract_keywords(q), entities=extract_entities(q))
    texts = " ".join(r.get("text", "") for r in res)
    check("Code of conduct retrieved", "code of conduct" in texts.lower())
    check("Source is employee_handbook.pdf", any((r.get("metadata") or {}).get("source") == "employee_handbook.pdf" for r in res))

    # TEST 7: Cross-document Retrieval (Resume + Company Policy)
    print("\n--- TEST 7: Cross-Document Evidence Retrieval ---")
    q = "Tell me the employee name and employee ID"
    res = retrieve(q, query_keywords=extract_keywords(q), entities=extract_entities(q), top_k=8)
    texts = " ".join(r.get("text", "") for r in res)
    sources = {(r.get("metadata") or {}).get("source") for r in res}
    check("Name in combined evidence", "Prajwal" in texts)
    check("ID in combined evidence", "EMP1024" in texts)
    check("Multiple sources retrieved", "resume.txt" in sources and "company_policy.pdf" in sources, f"sources: {sources}")

    # TEST 8: Duplicate Document Upload Protection
    print("\n--- TEST 8: Duplicate Document Protection ---")
    with open(os.path.join(TEST_DATA, "resume.txt"), "rb") as f:
        resume_content = f.read()
    dup_id = file_hash(resume_content)
    check("Duplicate file recognized as already indexed", document_exists(dup_id))

    # TEST 9: Query Normalization with Varied Phrasing
    print("\n--- TEST 9: Query Normalization with Varied Phrasing ---")
    phrasings = [
        "What is my name?",
        "What is the candidate's name?",
        "Tell me the candidate name",
        "Who is the applicant?",
    ]
    for ph in phrasings:
        kw = extract_keywords(ph)
        ent = extract_entities(ph)
        exp = expand_query(ph, keywords=kw, entities=ent)
        res = retrieve(ph, expanded_queries=exp, query_keywords=kw, entities=ent)
        texts = " ".join(r.get("text", "") for r in res)
        check(f"Phrasing '{ph}' retrieves name", "Prajwal" in texts, f"got: {texts[:80]}")

    # TEST 10: Exact Code / Identifier Lookup
    print("\n--- TEST 10: Exact Identifier Lookup ---")
    code_queries = [
        ("What is EMP1024?", "EMP1024"),
        ("What is the health insurance amount?", "50,000"),
        ("What is the salary amount?", "4,500"),
    ]
    for cq, expected_token in code_queries:
        ent = extract_entities(cq)
        kw = extract_keywords(cq)
        res = retrieve(cq, entities=ent, query_keywords=kw)
        texts = " ".join(r.get("text", "") for r in res)
        check(f"Query '{cq}' contains '{expected_token}'", expected_token in texts, f"got: {texts[:80]}")

    # TEST 11: Table Data Extraction (DOCX)
    print("\n--- TEST 11: Table Data Retrieval (DOCX) ---")
    q = "What is the price of Hex Bolt M12?"
    ent = extract_entities(q)
    kw = extract_keywords(q)
    res = retrieve(q, entities=ent, query_keywords=kw)
    texts = " ".join(r.get("text", "") for r in res)
    check("Hex Bolt price in table evidence", "Hex Bolt" in texts and ("1.50" in texts or "$1.50" in texts), f"got: {texts[:100]}")

    # TEST 12: Follow-up Question Resolution
    print("\n--- TEST 12: Follow-up Question Resolution ---")
    history = [
        {"role": "user", "content": "What is the candidate's name in the resume?"},
        {"role": "assistant", "content": "The candidate is Prajwal M. S. Yadav."},
    ]
    resolved = resolve_follow_up("What is his experience?", history)
    check("Follow-up references resolved with prior subject", "candidate" in resolved.lower() or "resume" in resolved.lower() or "name" in resolved.lower())

    res = retrieve(resolved, query_keywords=extract_keywords(resolved), entities=extract_entities(resolved))
    texts = " ".join(r.get("text", "") for r in res)
    check("Experience retrieved from resume", "Full Stack" in texts or "TechCorp" in texts, f"got: {texts[:100]}")

    # SUMMARY
    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:")
        for f in FAILURES:
            print(f"  - {f}")
    print("=" * 60)

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
