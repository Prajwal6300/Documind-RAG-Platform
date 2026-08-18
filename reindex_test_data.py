import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from rag.vector_store import list_documents, remove_document
from rag.chunker import create_chunks
from rag.document_loader import load_document
from rag.vector_store import add_chunks, register_document, document_exists

TEST_DATA = "test_data"


def file_hash(content):
    return hashlib.sha256(content).hexdigest()


def reindex(path):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    labels = {"pdf": "PDF", "docx": "DOCX", "txt": "TXT"}

    for doc in list_documents():
        if doc["source"] == name:
            remove_document(doc["id"])
            print(f"removed old {name}")

    with open(path, "rb") as f:
        content = f.read()

    doc_id = file_hash(content)
    pages = load_document(path)
    chunks = create_chunks(pages, name, document_id=doc_id, chunk_size=700, overlap=120)
    add_chunks(chunks)
    register_document(
        doc_id=doc_id,
        source=name,
        file_type=labels.get(ext, ext.upper()),
        page_count=len(pages),
        chunk_count=len(chunks),
    )
    print(f"reindexed {name}: {len(pages)} page(s), {len(chunks)} chunk(s)")


for f in os.listdir(TEST_DATA):
    path = os.path.join(TEST_DATA, f)
    if os.path.isfile(path):
        reindex(path)

print("\nRegistered documents:")
for d in list_documents():
    print(f"  - {d['source']} ({d['type']}) chunks={d['chunk_count']}")
