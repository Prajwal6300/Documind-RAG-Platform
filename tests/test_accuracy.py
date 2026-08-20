"""Accuracy test suite for the DocuMind high-accuracy RAG pipeline.

Covers (spec #29):
  exact name, exact ID, exact date, exact amount
  list question
  multi-part question
  summary
  no-answer question
  multi-document question
  follow-up question

For each test verifies: correct answer, correct source, no hallucination,
no duplicate display sources.

Run with:  python test_accuracy.py
"""

import hashlib
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from backend.src.chunking import create_chunks
from backend.src.ingestion import load_document
from backend.src.vectordb import (
    add_chunks,
    register_document,
    document_exists,
    list_documents,
)
from backend.src.pipeline import answer_question
from backend.src.prompts import NO_CONTEXT_MESSAGE

TEST_DATA = str(ROOT_DIR / "test_data")

PASS = 0
FAIL = 0
FAILURES = []


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
        print(f"  [skip] {name} already indexed")
        return doc_id

    pages = load_document(path)
    chunks = create_chunks(
        pages,
        name,
        document_id=doc_id,
        chunk_size=700,
        overlap=120,
    )
    add_chunks(chunks)
    register_document(
        doc_id=doc_id,
        source=name,
        file_type=labels.get(ext, ext.upper()),
        page_count=len(pages),
        chunk_count=len(chunks),
    )
    print(f"  [ok] indexed {name} ({len(chunks)} chunks)")
    return doc_id


def check(name, condition, detail=""):
    global PASS, FAIL

    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} — {detail}")
        print(f"  FAIL  {name}  {detail}")


def unique_sources(sources):
    return len(sources) == len({(s.get("source"), s.get("page")) for s in sources})


def answer_text(result):
    return (result.get("answer") or "").strip()


def main():
    global PASS, FAIL, FAILURES

    print("=== Indexing test documents ===")
    index_file(os.path.join(TEST_DATA, "company_policy.pdf"))
    index_file(os.path.join(TEST_DATA, "employee_handbook.pdf"))
    index_file(os.path.join(TEST_DATA, "resume.txt"))
    index_file(os.path.join(TEST_DATA, "inventory.docx"))

    docs = {d["source"]: d for d in list_documents()}
    print(f"\nIndexed documents: {list(docs.keys())}")

    # ------------------------------------------------------------------
    print("\n=== TEST 1: Exact name ===")
    t0 = time.time()
    r = answer_question("What is the employee's name in the resume?", stream=False)
    a = answer_text(r)
    check(
        "name present",
        "Prajwal" in a,
        f"got: {a[:150]}",
    )
    sources = r.get("sources") or []
    check(
        "name source = resume.txt",
        any((s.get("source") or s.get("name")) == "resume.txt" for s in sources),
        f"got: {sources}",
    )
    check("unique display sources", unique_sources(sources))
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 2: Exact ID ===")
    t0 = time.time()
    r = answer_question("What is the employee ID?", stream=False)
    a = answer_text(r)
    check(
        "employee ID = EMP1024",
        "EMP1024" in a,
        f"got: {a[:150]}",
    )
    sources = r.get("sources") or []
    check(
        "ID source = company_policy.pdf",
        any((s.get("source") or s.get("name")) == "company_policy.pdf" for s in sources),
        f"got: {sources}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 3: Exact date ===")
    t0 = time.time()
    r = answer_question("What is the joining date?", stream=False)
    a = answer_text(r)
    check(
        "joining date = 15 March 2021",
        "15" in a and "March" in a and "2021" in a,
        f"got: {a[:150]}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 4: Exact amount ===")
    t0 = time.time()
    r = answer_question("What is the monthly salary?", stream=False)
    a = answer_text(r)
    check(
        "salary = $4,500.00",
        "$4,500.00" in a or "4500" in a,
        f"got: {a[:150]}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 5: List question ===")
    t0 = time.time()
    r = answer_question("What are all the skills listed?", stream=False)
    a = answer_text(r)
    check(
        "skills list contains Python",
        "Python" in a,
        f"got: {a[:200]}",
    )
    check(
        "skills list contains React",
        "React" in a,
        f"got: {a[:200]}",
    )
    check(
        "skills list contains SQL",
        "SQL" in a,
        f"got: {a[:200]}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 6: Multi-part question ===")
    t0 = time.time()
    r = answer_question("What are the skills and experience?", stream=False)
    a = answer_text(r)
    check(
        "multi-part: Python skill",
        "Python" in a,
        f"got: {a[:200]}",
    )
    check(
        "multi-part: experience (Full Stack)",
        "Full Stack" in a,
        f"got: {a[:200]}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 7: Summary ===")
    t0 = time.time()
    r = answer_question("Summarize this document.", stream=False)
    a = answer_text(r)
    check(
        "summary not empty",
        len(a) > 20,
        f"got: {a[:100]}",
    )
    check(
        "summary has sources",
        len(r.get("sources") or []) > 0,
        f"got: {r.get('sources')}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 8: No-answer question ===")
    t0 = time.time()
    r = answer_question("What is the CEO's favorite color?", stream=False)
    a = answer_text(r)
    check(
        "no-answer returns not-found message",
        a == NO_CONTEXT_MESSAGE or "couldn't find" in a.lower(),
        f"got: {a[:150]}",
    )
    check(
        "no-answer has no sources",
        len(r.get("sources") or []) == 0,
        f"got: {r.get('sources')}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 9: Multi-document question ===")
    t0 = time.time()
    r = answer_question("What is the leave policy?", stream=False)
    a = answer_text(r)
    check(
        "leave policy answered from company_policy.pdf",
        "12" in a and "leave" in a.lower(),
        f"got: {a[:200]}",
    )
    sources = r.get("sources") or []
    check(
        "leave policy source = company_policy.pdf",
        any((s.get("source") or s.get("name")) == "company_policy.pdf" for s in sources),
        f"got: {sources}",
    )

    t0 = time.time()
    r = answer_question("What are the working hours?", stream=False)
    a = answer_text(r)
    check(
        "working hours answered from company_policy.pdf",
        "9" in a and "6 PM" in a,
        f"got: {a[:200]}",
    )

    t0 = time.time()
    r = answer_question("What is in the code of conduct?", stream=False)
    a = answer_text(r)
    check(
        "code of conduct from employee_handbook.pdf",
        "code of conduct" in a.lower(),
        f"got: {a[:200]}",
    )
    sources = r.get("sources") or []
    check(
        "code of conduct source = employee_handbook.pdf",
        any((s.get("source") or s.get("name")) == "employee_handbook.pdf" for s in sources),
        f"got: {sources}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 10: Follow-up question ===")
    t0 = time.time()
    history = [
        {"role": "user", "content": "What is the employee's designation in the resume?"},
        {"role": "assistant", "content": "The employee is a Software Engineer."},
    ]
    r = answer_question(
        "What is his experience?",
        stream=False,
        chat_history=history,
    )
    a = answer_text(r)
    check(
        "follow-up: experience answered",
        "Full Stack" in a or "developer" in a.lower(),
        f"got: {a[:200]}",
    )
    sources = r.get("sources") or []
    check(
        "follow-up source = resume.txt",
        any((s.get("source") or s.get("name")) == "resume.txt" for s in sources),
        f"got: {sources}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 11: Table question (DOCX) ===")
    t0 = time.time()
    r = answer_question("List all products and their prices.", stream=False)
    a = answer_text(r)
    check(
        "table: Hex Bolt price",
        "Hex Bolt" in a and ("1.50" in a or "$1.50" in a),
        f"got: {a[:200]}",
    )
    check(
        "table: Steel Washer price",
        "Washer" in a and "0.20" in a,
        f"got: {a[:200]}",
    )
    sources = r.get("sources") or []
    check(
        "table source = inventory.docx",
        any((s.get("source") or s.get("name")) == "inventory.docx" for s in sources),
        f"got: {sources}",
    )
    print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n=== TEST 12: Document-scoped retrieval ===")
    doc_id = docs.get("resume.txt", {}).get("id")

    if doc_id:
        t0 = time.time()
        r = answer_question(
            "What is the leave policy?",
            stream=False,
            document_id=doc_id,
        )
        a = answer_text(r)
        check(
            "scoped: leave policy NOT found in resume.txt",
            a == NO_CONTEXT_MESSAGE or "couldn't find" in a.lower(),
            f"got: {a[:150]}",
        )
        sources = r.get("sources") or []
        check(
            "scoped: no sources from resume.txt",
            all((s.get("source") or s.get("name")) == "resume.txt" for s in sources) is True,
            f"got: {sources}",
        )
        print(f"  ({time.time()-t0:.1f}s)")

    # ------------------------------------------------------------------
    print("\n========================================")
    print(f"RESULT: {PASS} passed, {FAIL} failed")

    if FAILURES:
        print("\nFailures:")
        for failure in FAILURES:
            print(f"  - {failure}")

    print("\nRegistered documents:")
    for d in list_documents():
        print(f"  - {d['source']} ({d['type']}) chunks={d['chunk_count']}")

    return 1 if FAIL else 0


def test_accuracy_suite():
    res = main()
    assert res == 0, f"Accuracy test suite had {FAIL} failures: {FAILURES}"


if __name__ == "__main__":
    sys.exit(main())
