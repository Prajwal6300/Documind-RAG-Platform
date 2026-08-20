import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.stdout.reconfigure(encoding="utf-8")

from backend.src.pipeline import answer_question


def run_followup_test():
    history = [
        {"role": "user", "content": "What is the employee''s designation in the resume?"},
        {"role": "assistant", "content": "The employee is a Software Engineer."},
    ]

    r = answer_question("What is his experience?", stream=False, chat_history=history, debug=True)
    print("A:", r["answer"][:300])
    print("no_context:", r["no_context"])
    dbg = r.get("debug") or {}
    print("resolved:", dbg.get("resolved_question"))
    print("sources:", r.get("sources"))
    return r


def test_followup():
    r = run_followup_test()
    assert r is not None


if __name__ == "__main__":
    run_followup_test()
