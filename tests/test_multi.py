import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.stdout.reconfigure(encoding="utf-8")

from backend.src.ingestion import load_document
from backend.src.chunking import create_chunks
from backend.src.vectordb import add_chunks, register_document, list_documents, document_exists, clear_all_documents
from backend.src.retrieval import retrieve
from backend.src.pipeline import answer_question
from backend.src.embeddings import embed_query

TEST_DATA_DIR = ROOT_DIR / "test_data"


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

    pages = load_document(str(path))
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
    return result


def run_multi_test():
    # Test 1: TXT document
    print("=== TEST: TXT Document ===")
    policy_path = str(TEST_DATA_DIR / "employee_policy.txt")
    txt_id = index_file(policy_path)
    ask("How many casual leaves are allowed per year?", txt_id)
    ask("What are the working hours?")

    # Test 2: Duplicate upload detection
    print("=== TEST: Duplicate Upload ===")
    txt_id_2 = index_file(policy_path)
    print(f"Same doc_id: {txt_id == txt_id_2}")
    assert txt_id == txt_id_2
    print()

    # Test 3: Document-scoped retrieval
    print("=== TEST: Document-Scoped Retrieval ===")
    ask("What is the leave policy?", txt_id)

    # Test 4: Question not in document
    print("=== TEST: Question Not In Document ===")
    ask("What is the CEO''s phone number?", txt_id)

    # Test 5: Multiple documents
    print("=== TEST: Multiple Documents ===")
    resume_path = str(TEST_DATA_DIR / "resume.txt")
    resume_id = index_file(resume_path)

    # Ask across all docs
    ask("How many casual leaves are allowed per year?")

    # Ask scoped to resume
    ask("What skills are listed?", resume_id)
    ask("How many casual leaves are allowed?", resume_id)  # should say not found

    # Verify documents list
    print("=== Registered Documents ===")
    docs = list_documents()
    for d in docs:
        print(f"  - {d['source']} ({d['type']}) pages={d['page_count']} chunks={d['chunk_count']}")

    print("\nDone!")
    return True


def test_multi_documents():
    assert run_multi_test() is True


if __name__ == "__main__":
    run_multi_test()
