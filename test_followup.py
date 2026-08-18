import sys

sys.stdout.reconfigure(encoding="utf-8")

from rag.rag_pipeline import answer_question

history = [
    {"role": "user", "content": "What is the employee's designation in the resume?"},
    {"role": "assistant", "content": "The employee is a Software Engineer."},
]

r = answer_question("What is his experience?", stream=False, chat_history=history, debug=True)
print("A:", r["answer"][:300])
print("no_context:", r["no_context"])
dbg = r.get("debug") or {}
print("resolved:", dbg.get("resolved_question"))
print("sources:", r.get("sources"))
