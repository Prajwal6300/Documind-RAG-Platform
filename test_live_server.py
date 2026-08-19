"""Live end-to-end HTTP client test for DocuMind backend and RAG pipeline."""

import time
import json
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

print("=" * 70)
print("LIVE END-TO-END SERVER VERIFICATION")
print("=" * 70)

# 1. Health Check
print("\n[1] Testing GET /api/health...")
res = requests.get(f"{BASE_URL}/api/health", timeout=10)
print("HTTP Status:", res.status_code)
print("Health Response:", json.dumps(res.json(), indent=2))
assert res.status_code == 200, "Health check failed"

# 2. Upload Document
test_file = Path("test_data/company_policy.pdf")
print(f"\n[2] Uploading real document: {test_file.name} via POST /api/documents/upload...")
with open(test_file, "rb") as f:
    files = {"file": (test_file.name, f, "application/pdf")}
    data = {"title": "Company Policy 2025"}
    upload_res = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data, timeout=30)

print("HTTP Status:", upload_res.status_code)
upload_json = upload_res.json()
print("Upload Response:", json.dumps(upload_json, indent=2))
doc_id = upload_json["id"]

# 3. Poll until indexed
print("\n[3] Polling GET /api/documents/:id until status is Indexed...")
for i in range(20):
    time.sleep(1)
    status_res = requests.get(f"{BASE_URL}/api/documents/{doc_id}", timeout=10)
    doc_data = status_res.json()
    status = doc_data.get("status")
    print(f"  Attempt {i+1}: Status={status}, Pages={doc_data.get('pages')}, Chunks={doc_data.get('chunks')}")
    if status in ("Indexed", "Failed"):
        break

assert doc_data.get("status") == "Indexed", f"Document failed to index: {doc_data.get('errorMessage')}"
print("Document is fully indexed in ChromaDB and SQLite!")

# 4. In-domain Grounded Chat
print("\n[4] Testing POST /api/chat with Grounded In-Domain Query...")
chat_payload = {
    "message": "What is the policy for sick leave, casual leave, and annual leave?",
    "scope": "All Documents"
}
chat_res = requests.post(f"{BASE_URL}/api/chat", json=chat_payload, timeout=60)
print("HTTP Status:", chat_res.status_code)
chat_json = chat_res.json()
session_id = chat_json.get("sessionId")
msg = chat_json.get("message", {})

print("\n--- GROUNDED RESPONSE ---")
print("Session ID:", session_id)
print("Intro:", msg.get("intro"))
print("Sections Count:", len(msg.get("sections", [])))
print("Sections:", json.dumps(msg.get("sections"), indent=2))
print("Sources:", json.dumps(msg.get("sources"), indent=2))
print("Groundedness:", json.dumps(msg.get("groundedness"), indent=2))
print("NoContext:", msg.get("noContext"))
assert msg.get("noContext") is False, "Expected grounded response"
assert len(msg.get("sources", [])) > 0, "Expected citations"

# 5. Out-of-Domain Refusal Check
print("\n[5] Testing POST /api/chat with Out-of-Domain Query...")
unrelated_payload = {
    "message": "What is the speed of light in a vacuum and who discovered it?",
    "scope": "All Documents",
    "session_id": session_id
}
unrelated_res = requests.post(f"{BASE_URL}/api/chat", json=unrelated_payload, timeout=30)
print("HTTP Status:", unrelated_res.status_code)
unrelated_json = unrelated_res.json()
unrelated_msg = unrelated_json.get("message", {})
print("\n--- OUT-OF-DOMAIN RESPONSE ---")
print("Intro:", unrelated_msg.get("intro"))
print("Sources:", json.dumps(unrelated_msg.get("sources")))
print("NoContext:", unrelated_msg.get("noContext"))
assert unrelated_msg.get("noContext") is True or "couldn't find" in unrelated_msg.get("intro", "").lower(), "Expected refusal"

# 6. SSE Streaming Chat
print("\n[6] Testing POST /api/chat/stream (Server-Sent Events)...")
stream_payload = {
    "message": "What are the standard working hours and lunch break?",
    "scope": "All Documents",
    "session_id": session_id
}
stream_res = requests.post(f"{BASE_URL}/api/chat/stream", json=stream_payload, stream=True, timeout=60)
print("HTTP Status:", stream_res.status_code)
print("Streaming Events received:")
events = []
for line in stream_res.iter_lines():
    if line:
        line_str = line.decode("utf-8")
        if line_str.startswith("data: "):
            event_data = json.loads(line_str[6:])
            events.append(event_data)
            if event_data.get("type") == "token":
                print(event_data.get("token"), end="", flush=True)

print(f"\nTotal SSE events received: {len(events)}")
assert len(events) > 0, "Expected SSE events"

# 7. Suggested Questions
print("\n\n[7] Testing GET /api/suggested-questions...")
sq_res = requests.get(f"{BASE_URL}/api/suggested-questions", timeout=10)
print("Suggested Questions:", json.dumps(sq_res.json(), indent=2))

# 8. Observability Logs
print("\n[8] Testing GET /api/logs...")
logs_res = requests.get(f"{BASE_URL}/api/logs?lines=10", timeout=10)
print("Recent Telemetry Logs:", json.dumps(logs_res.json(), indent=2))

print("\n" + "=" * 70)
print("ALL LIVE SERVER END-TO-END TESTS PASSED WITH 100% SUCCESS!")
print("=" * 70)
