import asyncio
import json
import sqlite3
import hashlib
import re
import datetime
from config import DB_PATH

def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db_connect()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tarefas (
                    task_id INTEGER PRIMARY KEY,
                    answers TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS questoes_resolvidas (
                    question_hash TEXT PRIMARY KEY,
                    question_type TEXT,
                    question_statement TEXT,
                    answer_data TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tarefas_ai (
                    task_id INTEGER PRIMARY KEY,
                    answers TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS questoes_ai (
                    question_hash TEXT PRIMARY KEY,
                    question_type TEXT,
                    question_statement TEXT,
                    answer_data TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leiasp_quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    question_id TEXT,
                    question_text TEXT,
                    question_type TEXT,
                    options_json TEXT,
                    answer_json TEXT,
                    created_at TEXT,
                    UNIQUE(book_id, question_id)
                )
            """)
    finally:
        conn.close()

async def db_call(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)

def _normalize_text_for_hash(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text

def make_question_hash(q_type: str, statement: str, options: any) -> str:
    """Generate a deterministic SHA256 hash for a question statement + options."""
    stmt_clean = _normalize_text_for_hash(statement)
    opts_clean = ""
    if isinstance(options, dict):
        items = []
        for k, v in sorted(options.items(), key=lambda x: str(x[0])):
            if isinstance(v, dict):
                items.append(f"{k}:{_normalize_text_for_hash(v.get('statement', ''))}")
            else:
                items.append(f"{k}:{_normalize_text_for_hash(str(v))}")
        opts_clean = "|".join(items)
    elif isinstance(options, list):
        opts_clean = "|".join(_normalize_text_for_hash(str(x)) for x in options)
    
    raw = f"{q_type}::{stmt_clean}::{opts_clean}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def resolve_cached_answers(task_data: dict, task_id: int) -> tuple[dict, bool]:
    """Look up cached answers for the given task. Returns (answers_dict, has_all_cached)."""
    is_essay = task_data.get("is_essay") or task_data.get("task_is_essay") or any(
        q.get("type") == "essay" for q in task_data.get("questions", [])
    )
    if is_essay:
        return {}, False

    questions = [q for q in task_data.get("questions", []) if q.get("type") not in ("info", "section")]
    if not questions:
        return {}, False

    resolved = {}
    conn = db_connect()
    try:
        row = conn.execute("SELECT answers FROM tarefas WHERE task_id = ?", (task_id,)).fetchone()
        if row and row["answers"]:
            try:
                data = json.loads(row["answers"])
                if isinstance(data, dict):
                    resolved.update(data)
            except Exception:
                pass

        for q in questions:
            qid = str(q.get("id"))
            if qid in resolved:
                continue
            q_type = q.get("type")
            if q_type in ("text_ai", "essay"):
                continue
            q_hash = make_question_hash(q_type, q.get("statement", ""), q.get("options"))
            
            row_q = conn.execute("SELECT answer_data FROM questoes_resolvidas WHERE question_hash = ?", (q_hash,)).fetchone()
            if not row_q:
                row_q = conn.execute("SELECT answer_data FROM questoes_ai WHERE question_hash = ?", (q_hash,)).fetchone()
            
            if row_q and row_q["answer_data"]:
                try:
                    ans_entry = json.loads(row_q["answer_data"])
                    resolved[qid] = ans_entry
                except Exception:
                    pass

        if len(resolved) < len(questions):
            row_ai = conn.execute("SELECT answers FROM tarefas_ai WHERE task_id = ?", (task_id,)).fetchone()
            if row_ai and row_ai["answers"]:
                try:
                    data = json.loads(row_ai["answers"])
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if str(k) not in resolved:
                                resolved[str(k)] = v
                except Exception:
                    pass

    finally:
        conn.close()

    has_all_cached = all(str(q.get("id")) in resolved for q in questions)
    return resolved, has_all_cached

def save_ai_cached_answers(task_id: int, answers: dict):
    """Save AI-generated answers for a task."""
    conn = db_connect()
    try:
        with conn:
            conn.execute("""
                INSERT INTO tarefas_ai (task_id, answers, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET answers = excluded.answers, created_at = excluded.created_at
            """, (task_id, json.dumps(answers, ensure_ascii=False), datetime.datetime.now(datetime.timezone.utc).isoformat()))
    finally:
        conn.close()

def save_question_level_ai_answers(task_data: dict, answers: dict):
    """Save AI answers by question hash for cross-task caching."""
    questions = task_data.get("questions", [])
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = db_connect()
    try:
        with conn:
            for q in questions:
                q_id = str(q.get("id"))
                q_type = q.get("type")
                if q_type in ("info", "section", "text_ai", "essay"):
                    continue
                if q_id in answers:
                    q_hash = make_question_hash(q_type, q.get("statement", ""), q.get("options"))
                    ans_data = json.dumps(answers[q_id], ensure_ascii=False)
                    conn.execute("""
                        INSERT INTO questoes_ai (question_hash, question_type, question_statement, answer_data, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(question_hash) DO UPDATE SET answer_data = excluded.answer_data, created_at = excluded.created_at
                    """, (q_hash, q_type, q.get("statement", "")[:500], ans_data, now))
    finally:
        conn.close()

def get_cached_leiasp_quiz_answer(book_id: int, question_id: any) -> any:
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT answer_json, question_type FROM leiasp_quizzes WHERE book_id = ? AND question_id = ?",
            (int(book_id), str(question_id))
        ).fetchone()
        if row and row["answer_json"]:
            try:
                return json.loads(row["answer_json"])
            except Exception:
                return row["answer_json"]
        return None
    finally:
        conn.close()

def save_cached_leiasp_quiz_answer(book_id: int, question_id: any, question_text: str, question_type: str, options: any, answer: any):
    conn = db_connect()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
                INSERT INTO leiasp_quizzes (book_id, question_id, question_text, question_type, options_json, answer_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, question_id) DO UPDATE SET
                    question_text = excluded.question_text,
                    question_type = excluded.question_type,
                    options_json = excluded.options_json,
                    answer_json = excluded.answer_json,
                    created_at = excluded.created_at
            """, (
                int(book_id),
                str(question_id),
                question_text[:500] if question_text else "",
                str(question_type) if question_type else "objective",
                json.dumps(options, ensure_ascii=False) if options else "",
                json.dumps(answer, ensure_ascii=False) if not isinstance(answer, str) else answer,
                now
            ))
    finally:
        conn.close()

