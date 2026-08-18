import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from rag.document_loader import load_document
from rag.chunker import create_chunks
from rag.vector_store import add_chunks, register_document, list_documents, document_exists, clear_all_documents
from rag.retriever import retrieve
from rag.rag_pipeline import answer_question
from rag.embeddings import embed_query


def file_hash(content):
    import hashlib
    return hashlib.sha256(content).hexdigest()


def index_file(path):
    with open(path, "rb") as f:
        content = f.read()
    doc_id = file_hash(content)
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lstrip(".").lower()

    if document_exists(doc_id):
        print(f"[SKIP] {name} already indexed")
        return doc_id

    pages = load_document(path)
    chunks = create_chunks(pages, name, document_id=doc_id, chunk_size=700, overlap=120)
    add_chunks(chunks)
    register_document(
        doc_id=doc_id,
        source=name,
        file_type=ext.upper(),
        page_count=len(pages),
        chunk_count=len(chunks),
    )
    print(f"[OK] Indexed {name}: {len(pages)} page(s), {len(chunks)} chunk(s)")
    return doc_id


def ask(question, doc_id=None):
    result = answer_question(question, stream=False, document_id=doc_id)
    print(f"\nQ: {question}")
    print(f"A: {result['answer']}")
    print(f"Sources: {result['sources']}")
    if result["no_context"]:
        print("  (no context found)")
    print()


clear_all_documents()

# Test 1: TXT document
print("=== TEST: TXT Document ===")
txt_id = index_file("employee_policy.txt")
ask("How many casual leaves are allowed per year?", txt_id)
ask("What are the working hours?")

# Test 2: Duplicate upload detection
print("=== TEST: Duplicate Upload ===")
txt_id_2 = index_file("employee_policy.txt")
print(f"Same doc_id: {txt_id == txt_id_2}")
print()

# Test 3: Document-scoped retrieval
print("=== TEST: Document-Scoped Retrieval ===")
ask("What is the leave policy?", txt_id)

# Test 4: Question not in document
print("=== TEST: Question Not In Document ===")
ask("What is the CEO's phone number?", txt_id)

# Test 5: Multiple documents
print("=== TEST: Multiple Documents ===")
resume_text = """Prajwal M. S. Yadav
Software Engineer
Skills: Python, React, Node.js, SQL
Education: B.Tech Computer Science
"""
with open("resume.txt", "w") as f:
    f.write(resume_text)
resume_id = index_file("resume.txt")

# Ask across all docs
ask("How many casual leaves are allowed per year?")

# Ask scoped to resume
ask("What skills are listed?", resume_id)
ask("How many casual leaves are allowed?", resume_id)  # should say not found

# Verify documents list
print("=== Registered Documents ===")
for d in list_documents():
    print(f"  - {d['source']} ({d['type']}) pages={d['page_count']} chunks={d['chunk_count']}")

print("\nDone!")
