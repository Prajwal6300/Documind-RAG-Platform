import time
import json
import sys
import requests
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run_server_proxy_e2e():
    print("=" * 70)
    print("VERIFYING BACKEND & FRONTEND PROXY INTEGRATION END-TO-END")
    print("=" * 70)

    # 1. Test Backend Direct
    print("\n[1] Testing Backend Direct (http://127.0.0.1:8000/api/health)...")
    res = requests.get("http://127.0.0.1:8000/api/health", timeout=10)
    print(f"Status: {res.status_code}")
    print("Body:", json.dumps(res.json(), indent=2))
    assert res.status_code == 200, "Backend health check failed"

    # 2. Test Frontend Root
    print("\n[2] Testing Frontend Root (http://localhost:5173)...")
    res = requests.get("http://localhost:5173", timeout=10)
    print(f"Status: {res.status_code}")
    assert res.status_code == 200, "Frontend root failed"
    assert 'id="root"' in res.text, "Frontend HTML does not contain root div"
    print("Frontend root HTML served successfully!")

    # 3. Test Frontend Proxy to Backend (/api/health)
    print("\n[3] Testing Frontend Proxy to Backend (http://localhost:5173/api/health)...")
    res = requests.get("http://localhost:5173/api/health", timeout=10)
    print(f"Status: {res.status_code}")
    print("Body:", json.dumps(res.json(), indent=2))
    assert res.status_code == 200, "Proxy /api/health failed"
    print("Proxy route /api/health succeeded!")

    # 4. Test Frontend Proxy Document List (/api/documents)
    print("\n[4] Testing Frontend Proxy Document List (http://localhost:5173/api/documents)...")
    res = requests.get("http://localhost:5173/api/documents", timeout=10)
    print(f"Status: {res.status_code}")
    docs = res.json()
    print(f"Found {len(docs)} existing documents in library.")
    assert res.status_code == 200, "Proxy /api/documents failed"

    # 5. Real Document Upload through Frontend Proxy (/api/documents/upload)
    test_file = ROOT_DIR / "test_data" / "company_policy.pdf"
    print(f"\n[5] Uploading real document '{test_file.name}' through Frontend Proxy (http://localhost:5173/api/documents/upload)...")
    with open(test_file, "rb") as f:
        files = {"file": (test_file.name, f, "application/pdf")}
        data = {"title": "Company Policy 2025 Verification"}
        res = requests.post("http://localhost:5173/api/documents/upload", files=files, data=data, timeout=30)

    print(f"Upload Status: {res.status_code}")
    upload_data = res.json()
    print("Upload Response:", json.dumps(upload_data, indent=2))
    assert res.status_code == 200, f"Upload failed: {upload_data}"
    doc_id = upload_data["id"]

    # 6. Poll until Indexed (up to 60s)
    print(f"\n[6] Polling document status for doc_id={doc_id} via proxy...")
    final_status = "Processing"
    for i in range(30):
        time.sleep(2)
        status_res = requests.get(f"http://localhost:5173/api/documents/{doc_id}", timeout=10)
        doc_info = status_res.json()
        final_status = doc_info.get("status")
        print(f"  Attempt {i+1} ({ (i+1)*2 }s): Status={final_status}, Chunks={doc_info.get('chunks')}")
        if final_status in ("Indexed", "Failed"):
            break

    assert final_status == "Indexed", f"Indexing failed: {doc_info}"
    print("Document successfully indexed in Supabase pgvector & PostgreSQL via proxy!")

    # 7. Ask a Question via Frontend Proxy Chat Endpoint
    print("\n[7] Querying Chat via Frontend Proxy (http://localhost:5173/api/chat)...")
    chat_res = requests.post("http://localhost:5173/api/chat", json={
        "message": "What is the policy for sick leave, casual leave, and annual leave?",
        "scope": doc_id
    }, timeout=60)
    print(f"Chat Status: {chat_res.status_code}")
    chat_data = chat_res.json()
    msg = chat_data.get("message", {})
    print("\n--- ASSISTANT GROUNDED RESPONSE ---")
    print("Intro:", msg.get("intro"))
    print("Groundedness:", json.dumps(msg.get("groundedness"), indent=2))
    print("Sources Count:", len(msg.get("sources", [])))
    print("Sources:", json.dumps(msg.get("sources"), indent=2))
    assert chat_res.status_code == 200, "Chat request failed"
    assert msg.get("noContext") is False, "Expected grounded response"
    assert len(msg.get("sources", [])) > 0, "Expected sources"

    # 8. Test Suggested Questions via Proxy
    print("\n[8] Testing GET /api/suggested-questions via proxy...")
    sq_res = requests.get("http://localhost:5173/api/suggested-questions", timeout=10)
    print(f"Status: {sq_res.status_code}")
    print("Suggested Questions Count:", len(sq_res.json()))
    assert sq_res.status_code == 200

    # 9. Test Chat Sessions List via Proxy
    print("\n[9] Testing GET /api/chat/sessions via proxy...")
    sessions_res = requests.get("http://localhost:5173/api/chat/sessions", timeout=10)
    print(f"Status: {sessions_res.status_code}")
    print("Sessions Count:", len(sessions_res.json()))
    assert sessions_res.status_code == 200

    print("\n" + "=" * 70)
    print("ALL LIVE SERVER AND PROXY TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


def test_server_and_proxy_e2e():
    try:
        res = requests.get("http://localhost:5173", timeout=1)
        if res.status_code != 200:
            pytest.skip("Frontend dev server at http://localhost:5173 is not running")
    except Exception:
        pytest.skip("Frontend / Backend servers not running for proxy test")
    run_server_proxy_e2e()


if __name__ == "__main__":
    run_server_proxy_e2e()
