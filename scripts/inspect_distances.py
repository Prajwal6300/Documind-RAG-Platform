import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.stdout.reconfigure(encoding="utf-8")

from backend.src.vectordb import get_collection, list_documents
from backend.src.embeddings import embed_query

collection = get_collection()

print("=== Collection metadata ===")
try:
    print(collection.metadata)
except Exception as e:
    print(f"metadata error: {e}")

print(f"\n=== Collection count: {collection.count()} ===")
for doc in list_documents():
    print(f"  - {doc['source']} ({doc['type']}) chunks={doc['chunk_count']}")

print("\n=== Distance inspection for known queries ===")

QUERIES = [
    "How many casual leaves are allowed per year?",
    "What are the working hours?",
    "What is the leave policy?",
    "What skills are listed?",
    "What is the CEO's phone number?",
]

for q in QUERIES:
    print(f"\nQ: {q}")
    emb = embed_query(q)
    res = collection.query(
        query_embeddings=[emb],
        n_results=5,
    )
    docs = res.get("documents", [[]])[0] or []
    metas = res.get("metadatas", [[]])[0] or []
    dists = res.get("distances", [[]])[0] or []
    for doc, meta, dist in zip(docs, metas, dists):
        src = meta.get("source", "?")
        page = meta.get("page")
        print(f"  d={dist:.4f}  {src} p={page}  | {doc[:70].replace(chr(10),' ')}")
