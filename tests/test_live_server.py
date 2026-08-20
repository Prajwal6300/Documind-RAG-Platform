"""Live end-to-end HTTP client test for DocuMind backend and RAG pipeline."""

import time
import json
import sys
import requests
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BASE_URL = "http://127.0.0.1:8000"


def run_live_server_test():
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
    test_file = ROOT_DIR / "test_data" / "company_policy.pdf"
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
    doc_data = {}
    for i in range(20):
        time.sleep(1)
        status_res = requests.get(f"{BASE_URL}/api/documents/{doc_id}", timeout=10)
        doc_data = status_res.json()
        status = doc_data.get("status")
        print(f"  Attempt {i+1}: Status={status}, Pages={doc_data.get('pages')}, Chunks={doc_data.get('chunks')}")
        if status in ("Indexed", "Failed"):
            break

    assert doc_data.get("status") == "Indexed", f"Document failed to index: {doc_data.get('errorMessage')}"
    print("Document is fully indexed in Supabase pgvector and PostgreSQL!")

    # 4. In-domain Grounded Chat
    print("\n[4] Testing POST /api/chat with Grounded In-Domain Query...")
    chat_payload = {
        "message": "What is the policy for sick leave, casual leave, and annual leave?",
        "scope": "All Documents"
    }
    chat_res = requests.post(f"{BASE_URL}/api/chat", json=chat_payload, timeout=60)
    print("HTTP Status:", chat_res.status_code)
    chat_json = chat_res.json()
    msg = chat_json.get("message", {})
    print("Answer Intro:", msg.get("intro"))
    print("Groundedness:", json.dumps(msg.get("groundedness"), indent=2))
    print("Sources:", json.dumps(msg.get("sources"), indent=2))
    assert chat_res.status_code == 200, "Chat request failed"
    assert msg.get("noContext") is False, "Expected grounded response"
    assert len(msg.get("sources", [])) > 0, "Expected sources"
    print("In-domain grounded chat test passed!")

    # 5. Out-of-domain Zero-Hallucination Refusal
    print("\n[5] Testing POST /api/chat with Out-of-Domain Query (Refusal Gate)...")
    refusal_payload = {
        "message": "What is the CEO's favorite color?",
        "scope": "All Documents"
    }
    ref_res = requests.post(f"{BASE_URL}/api/chat", json=refusal_payload, timeout=60)
    print("HTTP Status:", ref_res.status_code)
    ref_json = ref_res.json()
    ref_msg = ref_json.get("message", {})
    print("Refusal Answer:", ref_msg.get("intro"))
    assert ref_res.status_code == 200
    assert ref_msg.get("noContext") is True or "couldn't find" in ref_msg.get("intro", "").lower()
    print("Anti-hallucination refusal test passed!")

    print("\n" + "=" * 70)
    print("ALL LIVE END-TO-END VERIFICATION STEPS PASSED SUCCESSFULLY!")
    print("=" * 70)


def test_live_server():
    try:
        res = requests.get(f"{BASE_URL}/api/health", timeout=1)
        if res.status_code != 200:
            pytest.skip("Live server at http://127.0.0.1:8000 is not healthy")
    except Exception:
        pytest.skip("Live server is not currently running at http://127.0.0.1:8000")
    run_live_server_test()


if __name__ == "__main__":
    run_live_server_test()
