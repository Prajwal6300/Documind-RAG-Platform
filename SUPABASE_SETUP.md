# Supabase PostgreSQL + pgvector Setup Guide

This guide walks through configuring and verifying Supabase for DocuMind RAG Platform.

---

## 1. Prerequisites

1. A [Supabase](https://supabase.com) account and project.
2. The `pgvector` extension enabled on your database.

---

## 2. Enabling pgvector in Supabase

1. Open your **Supabase Dashboard** → Select your project.
2. Navigate to **Database** → **Extensions**.
3. Search for `vector` and click **Enable** (installs `pgvector 0.8.2+`).

Alternatively, execute in the **SQL Editor**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 3. Database Connection String

In the Supabase Dashboard:
1. Navigate to **Project Settings** → **Database** → **Connection string**.
2. Select **URI format**.
3. Choose **Transaction Pooler (Port 6543)** (Recommended for long-running servers and serverless backends):

```env
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

Add this to your local `.env` file at the project root.

---

## 4. Applying Schema Migrations

Run the automated migration runner:
```bash
python scripts/run_migrations.py
```

This applies [`migrations/001_initial_supabase_schema.sql`](file:///F:/RAG-Document-Chatbot/migrations/001_initial_supabase_schema.sql), which sets up:
- `documents` table
- `document_chunks` table with `vector` column and HNSW index
- `chat_sessions` and `chat_messages` tables
- Foreign key cascade deletions and performance indexes

---

## 5. Migrating Existing Data (Optional)

To migrate records from local SQLite (`data/documind.db`) and ChromaDB collections into Supabase:
```bash
python scripts/migrate_to_supabase.py
```

---

## 6. Verifying Database Connection

To verify connectivity and pgvector readiness:
```bash
python -c "import psycopg, os, dotenv; dotenv.load_dotenv(); conn = psycopg.connect(os.getenv('DATABASE_URL'), prepare_threshold=None); print('Connected:', conn.execute('SELECT version();').fetchone()[0]); conn.close()"
```

---

## 7. Running Evaluation and Verification

```bash
# Run End-to-End FastAPI Verification
python tests/test_e2e_verification.py
                                
# Run 35-Query Evaluation Benchmark
python scripts/eval.py
```
