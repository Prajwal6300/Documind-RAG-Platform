"""End-to-end verification script for DocuMind backend and RAG pipeline."""

import time
import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("=" * 70)
print("DOCUMIND RAG PIPELINE — END-TO-END VERIFICATION")
print("=" * 70)

# 1. Health Check
print("\n[STEP 1] Testing Health Endpoint: GET /api/health")
res = client.get("/api/health")
print("HTTP Status:", res.status_code)
print("Response:", json.dumps(res.json(), indent=2))
assert res.status_code == 200, "Health check failed"

# 2. List Documents Before Upload
print("\n[STEP 2] Testing List Documents: GET /api/documents")
res = client.get("/api/documents")
print("HTTP Status:", res.status_code)
print(f"Current documents count: {len(res.json())}")

# 3. Upload a Real Test Document
test_file_path = Path("test_data/company_policy.pdf")
if not test_file_path.exists():
    test_file_path = Path("test_data/employee_handbook.pdf")

print(f"\n[STEP 3] Uploading real document: {test_file_path.name}")
with open(test_file_path, "rb") as f:
    files = {"file": (test_file_path.name, f, "application/pdf")}
    res = client.post("/api/documents/upload", files=files, data={"title": "Company Policy 2024"})

print("HTTP Status:", res.status_code)
upload_json = res.json()
print("Upload Response:", json.dumps(upload_json, indent=2))
doc_id = upload_json["id"]

# 4. Wait for Background Indexing to complete
print("\n[STEP 4] Waiting for indexing pipeline to finish...")
for _ in range(15):
    time.sleep(2)
    doc_res = client.get(f"/api/documents/{doc_id}")
    doc_data = doc_res.json()
    status = doc_data.get("status")
    print(f"  Current status for {doc_id}: {status} (pages: {doc_data.get('pages')}, chunks: {doc_data.get('chunks')})")
    if status in ("Indexed", "Failed"):
        break

assert doc_data.get("status") == "Indexed", f"Document indexing failed: {doc_data.get('errorMessage')}"
print("Document successfully indexed with real pages and vector embeddings!")

# 5. Test Dynamic Suggested Questions
print("\n[STEP 5] Testing Suggested Questions: GET /api/suggested-questions")
sq_res = client.get("/api/suggested-questions")
print("Suggested Questions:", json.dumps(sq_res.json(), indent=2))
assert len(sq_res.json()) > 0, "Expected at least one suggested question"

# 6. Ask Grounded In-Domain Question
print("\n[STEP 6] Asking Grounded Question: 'What is the standard working hours and policy on leaves?'")
chat_payload = {
    "message": "What is the standard working hours and policy on leaves?",
    "scope": "All Documents",
}
chat_res = client.post("/api/chat", json=chat_payload)
print("HTTP Status:", chat_res.status_code)
chat_data = chat_res.json()
print("\n--- GROUNDED RESPONSE ---")
print("Intro:", chat_data["message"]["intro"])
print("\nSections:")
print(json.dumps(chat_data["message"]["sections"], indent=2))
print("\nSources Cited:")
print(json.dumps(chat_data["message"]["sources"], indent=2))
print("\nEvidences (Real chunk quotes):")
print(json.dumps(chat_data["message"]["evidences"], indent=2))
print("No Context Flag:", chat_data["message"]["noContext"])
assert chat_data["message"]["noContext"] is False, "Expected grounded response"
assert len(chat_data["message"]["sources"]) > 0, "Expected at least one source citation"

# 7. Ask Out-of-Domain / Unrelated Question
print("\n[STEP 7] Asking Unrelated Question: 'What is the formula for calculating quantum entanglement entropy in black holes?'")
unrelated_payload = {
    "message": "What is the formula for calculating quantum entanglement entropy in black holes?",
    "scope": "All Documents",
    "session_id": chat_data.get("sessionId")
}
unrelated_res = client.post("/api/chat", json=unrelated_payload)
print("HTTP Status:", unrelated_res.status_code)
unrelated_data = unrelated_res.json()
print("\n--- OUT-OF-DOMAIN RESPONSE ---")
print("Intro:", unrelated_data["message"]["intro"])
print("Sections:", json.dumps(unrelated_data["message"]["sections"]))
print("Sources:", json.dumps(unrelated_data["message"]["sources"]))
print("No Context Flag:", unrelated_data["message"]["noContext"])
assert unrelated_data["message"]["noContext"] is True or "couldn't find" in unrelated_data["message"]["intro"].lower(), "Expected refusal for out-of-domain query"

# 8. Test Recent Analysis / Chat History Persistence
print("\n[STEP 8] Testing Recent Analyses History: GET /api/chat/sessions")
sessions_res = client.get("/api/chat/sessions")
print("Recent Sessions:", json.dumps(sessions_res.json(), indent=2))
assert len(sessions_res.json()) > 0, "Expected persisted chat session in SQLite"

# 9. Test Archiving Document
print(f"\n[STEP 9] Testing Document Archive: POST /api/documents/{doc_id}/archive")
arc_res = client.post(f"/api/documents/{doc_id}/archive")
print("Archive result:", arc_res.json())

# Check that active documents list no longer includes the archived document
docs_after_arc = client.get("/api/documents").json()
archived_found_in_active = any(d["id"] == doc_id for d in docs_after_arc)
print(f"Archived document present in active list: {archived_found_in_active} (Expected False)")
assert not archived_found_in_active, "Archived document should not be in active list"

# Check that archive endpoint lists it
archive_items = client.get("/api/archive").json()
print(f"Total archived items: {len(archive_items)}")
assert any(item.get("rawId") == doc_id for item in archive_items), "Document should appear in archive"

# 10. Restore Document
print(f"\n[STEP 10] Restoring Document: POST /api/documents/{doc_id}/restore")
rest_res = client.post(f"/api/documents/{doc_id}/restore")
print("Restore result:", rest_res.json())

print("\n" + "=" * 70)
print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
print("=" * 70)
