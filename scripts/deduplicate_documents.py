"""Database document deduplication and cleanup utility for DocuMind.

Detects duplicate document records in PostgreSQL (Supabase) by content-hash,
name, and chunk text signatures.

Usage:
  python scripts/deduplicate_documents.py          # Dry-run report (no changes)
  python scripts/deduplicate_documents.py --apply  # Execute deletion of duplicate records
"""

import os
import sys
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.src.vectordb.database import get_db_connection, list_all_documents
from backend.src.utils.helpers import file_hash


def find_duplicates(conn):
    """Scan documents and chunks to find all duplicate groups."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name, title, type, size, size_bytes, pages, chunks, file_path, status, content_hash, created_at, is_archived
            FROM documents
            ORDER BY created_at ASC;
        """)
        all_docs = cur.fetchall()

        # Also get chunk count per doc from document_chunks
        cur.execute("""
            SELECT document_id, COUNT(*) as chunk_count, STRING_AGG(SUBSTRING(text, 1, 50), '||' ORDER BY chunk_index ASC) as sample_sig
            FROM document_chunks
            GROUP BY document_id;
        """)
        chunk_info = {r["document_id"]: r for r in cur.fetchall()}

    groups = defaultdict(list)

    for doc in all_docs:
        doc_id = doc["id"]
        file_p = doc.get("file_path", "")
        c_hash = doc.get("content_hash") or ""

        # Compute content hash from file if empty
        if not c_hash and file_p and os.path.exists(file_p):
            try:
                with open(file_p, "rb") as f:
                    c_hash = file_hash(f.read())
            except Exception:
                pass

        ci = chunk_info.get(doc_id, {})
        sig = ci.get("sample_sig") or ""

        # Group key: content_hash if available, else (name, type, size_bytes, chunk_sig)
        if c_hash:
            key = f"hash:{c_hash}"
        elif sig:
            key = f"sig:{doc['name']}:{ci.get('chunk_count', 0)}:{sig[:80]}"
        else:
            key = f"name:{doc['name']}:{doc.get('size_bytes', 0)}"

        doc_dict = dict(doc)
        doc_dict["computed_hash"] = c_hash
        doc_dict["actual_chunks"] = ci.get("chunk_count", 0)
        groups[key].append(doc_dict)

    return groups


def main():
    parser = argparse.ArgumentParser(description="DocuMind Document Deduplication Utility")
    parser.add_argument("--apply", action="store_true", help="Execute deletion of duplicate records (default: dry-run only)")
    args = parser.parse_args()

    print("=" * 70)
    print(" DocuMind Document Deduplication Utility")
    print(" Mode: " + ("EXECUTE DELETION (--apply)" if args.apply else "DRY-RUN (no modifications)"))
    print("=" * 70)

    try:
        with get_db_connection() as conn:
            groups = find_duplicates(conn)

            total_docs = sum(len(docs) for docs in groups.values())
            duplicate_groups = {k: docs for k, docs in groups.items() if len(docs) > 1}
            redundant_count = sum(len(docs) - 1 for docs in duplicate_groups.values())

            print(f"\nScan Summary:")
            print(f"  • Total Document Records in DB: {total_docs}")
            print(f"  • Unique Content Groups:        {len(groups)}")
            print(f"  • Duplicate Groups Identified:   {len(duplicate_groups)}")
            print(f"  • Redundant Records to Remove:  {redundant_count}\n")

            if not duplicate_groups:
                print(" No duplicate documents found in the database. Vector store is fully clean.")
                return

            to_delete_doc_ids = []
            to_delete_files = []

            for idx, (key, docs) in enumerate(duplicate_groups.items(), 1):
                # Sort docs so that records with actual chunks > 0, not archived, and valid files are kept as primary
                sorted_docs = sorted(
                    docs,
                    key=lambda d: (
                        1 if d.get("actual_chunks", 0) > 0 else 0,
                        1 if not d.get("is_archived") else 0,
                        1 if d.get("file_path") and os.path.exists(d["file_path"]) else 0,
                        d.get("created_at") or "",
                    ),
                    reverse=True,
                )
                primary = sorted_docs[0]
                redundant = sorted_docs[1:]

                print(f"Group #{idx}: '{primary['name']}' ({len(docs)} copies)")
                print(f"  [KEEP PRIMARY] ID: {primary['id']} (created: {primary['created_at']}, chunks: {primary['actual_chunks']})")
                for r in redundant:
                    print(f"  [PRUNE DUPLICATE] ID: {r['id']} (created: {r['created_at']}, chunks: {r['actual_chunks']})")
                    to_delete_doc_ids.append(r["id"])
                    if r.get("file_path") and r["file_path"] != primary.get("file_path") and os.path.exists(r["file_path"]):
                        to_delete_files.append(r["file_path"])
                print()

            if not args.apply:
                print("=" * 70)
                print(" DRY-RUN COMPLETE: No changes were made to the database.")
                print(f" {len(to_delete_doc_ids)} duplicate records would be removed.")
                print(" Run with '--apply' after confirmation to execute this cleanup.")
                print("=" * 70)
                return

            # Execute deletion
            print(f"Applying deduplication: deleting {len(to_delete_doc_ids)} records from database...")
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_chunks WHERE document_id = ANY(%s);", (to_delete_doc_ids,))
                cur.execute("DELETE FROM documents WHERE id = ANY(%s);", (to_delete_doc_ids,))

            # Clean up orphaned files
            for fp in to_delete_files:
                try:
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception as e:
                    print(f"  Warning: could not delete file {fp}: {e}")

            print(" Cleanup complete. All duplicate records and chunks removed successfully.")

    except Exception as e:
        print(f"Error during deduplication scan: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
