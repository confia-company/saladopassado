import asyncio
import base64
import json
import logging
import os
import random
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    BASE_DIR,
    SED_LOGIN_URL,
    SED_VALIDA_URL,
    SED_SUBSCRIPTION_KEY,
    IPTV_TOKEN_URL,
    IPTV_BASE_URL,
)
from client import HttpCloakClient, _get_browser_context, _generate_traceparent
from captcha_solver import tms_apply_with_captcha
from database import init_db, get_cached_leiasp_quiz_answer, save_cached_leiasp_quiz_answer
from ai_solver import resolve_task_answers, resolve_leiasp_objective, resolve_leiasp_dissertative
from matific_client import (
    MatificClient,
    translate_matific_slug,
    _aggregate_played_episodes
)
from leiasp_client import LeiaSPClient, LeiaSPAuthError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("saladopassado.app")

_sessions: dict[str, dict] = {}
_task_cache: dict[int, dict] = {}
_delayed_jobs: dict[str, dict] = {}

_matific_session_cache: dict[str, dict] = {}
_MATIFIC_SESSION_TTL = 20 * 60
_MATIFIC_EPISODES_TTL = 5 * 60
_MATIFIC_STATE_TTL = 3 * 60
_matific_locks: dict[str, asyncio.Lock] = {}
_matific_jobs: dict[str, dict] = {}
_matific_batches: dict[str, dict] = {}

_task_batches: dict[str, dict] = {}
_leiasp_jobs: dict[str, dict] = {}
_leiasp_locks: dict[str, asyncio.Lock] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized successfully.")
    yield

app = FastAPI(title="Sala do Passado — SalaDoPassado", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

async def get_current_user(request: Request) -> dict:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in _sessions:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_id = auth_header[7:].strip()
            
    if not session_id or session_id not in _sessions:
        raise HTTPException(status_code=401, detail="Sessão expirada ou não autenticado")
    return _sessions[session_id]

class LoginRequest(BaseModel):
    ra: str
    digito: str
    uf: str
    password: str

class SubmitRequest(BaseModel):
    answers: dict
    answer_id: Optional[int] = None
    duration: Optional[float] = None
    min_time: Optional[int] = None
    max_time: Optional[int] = None

class TaskBatchSolveRequest(BaseModel):
    task_ids: list[int]
    min_time: Optional[float] = None
    max_time: Optional[float] = None

class MatificCompleteRequest(BaseModel):
    episode: dict
    target_accuracy: Optional[str] = "realistic"
    timings: Optional[dict] = None

class MatificBatchRequest(BaseModel):
    episodes: list[dict]
    min_time_per_task: Optional[float] = 1.0
    max_time_per_task: Optional[float] = 3.0
    min_wait_between: Optional[float] = 0.2
    max_wait_between: Optional[float] = 1.0
    target_accuracy: Optional[str] = "realistic"

class MatificPurchaseRequest(BaseModel):
    campaign_id: str
    item_id: str
    cost: int

class MatificEquipRequest(BaseModel):
    campaign_id: str
    part_name: str
    item_id: str

class MatificRepairRequest(BaseModel):
    campaign_id: str

class MatificSetStatsRequest(BaseModel):
    campaign_id: str
    coins: Optional[int] = None
    xp: Optional[int] = None
    rank: Optional[int] = None

@app.get("/", response_class=HTMLResponse)
async def index_page():
    tpl_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.isfile(tpl_path):
        with open(tpl_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SalaDoPassado Backend Online</h1>"

@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    ra_clean = req.ra.strip().lstrip("0") or req.ra.strip()
    digito_clean = req.digito.strip()
    uf_clean = req.uf.strip().upper()
    constructed_user = f"{ra_clean}{digito_clean}{uf_clean}"

    fp = _get_browser_context()
    headers_login = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": SED_SUBSCRIPTION_KEY,
        "X-Product-Name": "SalaDoFuturo",
        "Origin": "https://saladofuturo.educacao.sp.gov.br",
        "Referer": "https://saladofuturo.educacao.sp.gov.br/",
        "User-Agent": fp["user-agent"],
        "sec-ch-ua": fp["sec-ch-ua"],
        "sec-ch-ua-mobile": fp["sec-ch-ua-mobile"],
        "sec-ch-ua-platform": fp["sec-ch-ua-platform"],
    }

    async with HttpCloakClient(timeout=20.0) as client:
        resp_sed = await client.post(
            SED_LOGIN_URL,
            json={"user": constructed_user, "senha": req.password},
            headers=headers_login
        )
        if resp_sed.status_code != 200:
            raise HTTPException(status_code=400, detail="Credenciais inválidas ou erro no servidor da SED.")

        data_sed = resp_sed.json()
        token_sed = data_sed.get("token")
        if not token_sed:
            raise HTTPException(status_code=400, detail="Usuário ou senha incorretos.")

        user_info = data_sed.get("DadosUsuario", {})
        student_name = user_info.get("NAME") or user_info.get("Nome") or "Estudante"

        headers_valida = dict(headers_login)
        headers_valida["Authorization"] = f"Bearer {token_sed}"
        await client.post(SED_VALIDA_URL, headers=headers_valida)

        leiasp_jwt = None
        try:
            url_leiasp = "https://sedintegracoes.educacao.sp.gov.br/saladofuturobffapi/integracoes/Token?plataforma=LeiaSP%2B"
            resp_tok = await client.get(url_leiasp, headers=headers_valida)
            if resp_tok.status_code == 200:
                leiasp_jwt = resp_tok.json().get("data")
        except Exception as e:
            logger.warning(f"[Login] Falha ao pré-obter LeiaSP JWT: {e}")

        headers_iptv = {
            "Content-Type": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Origin": "https://saladofuturo.educacao.sp.gov.br",
            "Referer": "https://saladofuturo.educacao.sp.gov.br/",
            "User-Agent": fp["user-agent"],
            "sec-ch-ua": fp["sec-ch-ua"],
            "sec-ch-ua-mobile": fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": fp["sec-ch-ua-platform"],
            "x-api-platform": "webclient",
            "x-api-realm": "edusp"
        }
        resp_iptv = await client.post(IPTV_TOKEN_URL, json={"token": token_sed}, headers=headers_iptv)
        if resp_iptv.status_code != 200:
            raise HTTPException(status_code=502, detail="Erro ao sincronizar token com a plataforma IPTV.")

        iptv_data = resp_iptv.json()
        auth_token = iptv_data.get("auth_token")
        nick = iptv_data.get("nick")

        if not auth_token or not nick:
            raise HTTPException(status_code=502, detail="Não foi possível obter os tokens da plataforma.")

        session_id = uuid.uuid4().hex
        user_session = {
            "session_id": session_id,
            "name": student_name,
            "username": constructed_user,
            "ra": ra_clean,
            "digito": digito_clean,
            "uf": uf_clean,
            "password": req.password,
            "token_sed": token_sed,
            "leiasp_jwt": leiasp_jwt,
            "auth_token": auth_token,
            "nick": nick,
            "room_name": "",
            "apply_times": {},
            "active_answer_ids": {},
        }
        _sessions[session_id] = user_session

        asyncio.create_task(_prewarm_matific_session(user_session))

        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=86400
        )

        return {
            "success": True,
            "token": session_id,
            "user": {
                "name": student_name,
                "ra": ra_clean,
                "digito": digito_clean,
                "uf": uf_clean,
                "nick": nick
            }
        }

@app.get("/api/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "name": user["name"],
        "ra": user["ra"],
        "digito": user["digito"],
        "uf": user["uf"],
        "nick": user["nick"]
    }

@app.post("/api/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    _sessions.pop(user.get("session_id"), None)
    response.delete_cookie("session_id")
    return {"success": True}

@app.get("/api/tasks")
async def list_tasks(user: dict = Depends(get_current_user)):
    fp = _get_browser_context()
    headers_tms = {
        "x-api-key": user["auth_token"],
        "x-api-platform": "webclient",
        "x-api-realm": "edusp",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "User-Agent": fp["user-agent"],
        "sec-ch-ua": fp["sec-ch-ua"],
        "sec-ch-ua-mobile": fp["sec-ch-ua-mobile"],
        "sec-ch-ua-platform": fp["sec-ch-ua-platform"],
    }

    async with HttpCloakClient(timeout=20.0) as client:
        url_rooms = f"{IPTV_BASE_URL}/room/user?list_all=true&with_cards=true"
        resp_rooms = await client.get(url_rooms, headers=headers_tms)
        if resp_rooms.status_code != 200:
            raise HTTPException(status_code=502, detail="Erro ao consultar salas do aluno.")

        rooms = resp_rooms.json().get("rooms", [])
        if rooms:
            user["room_name"] = rooms[0].get("name", user.get("room_name", ""))

        targets = []
        for r in rooms:
            rname = r.get("name")
            if rname:
                targets.append(f"publication_target={rname}")
                targets.append(f"publication_target={rname}:{user['nick']}")
            for cat in r.get("group_categories", []):
                cid = cat.get("id")
                if cid:
                    targets.append(f"publication_target={cid}")
        targets_query = "&".join(targets)

        url_tasks = f"{IPTV_BASE_URL}/tms/task/todo?expired_only=false&limit=100&offset=0&filter_expired=true&is_exam=false&with_answer=true&is_essay=false&{targets_query}&with_apply_moment=true"
        resp_tasks = await client.get(url_tasks, headers=headers_tms)
        tasks_raw = resp_tasks.json() if resp_tasks.status_code == 200 else []

        url_essays = f"{IPTV_BASE_URL}/tms/task/todo?expired_only=false&limit=100&offset=0&filter_expired=true&is_exam=false&with_answer=true&is_essay=true&{targets_query}&with_apply_moment=true"
        resp_essays = await client.get(url_essays, headers=headers_tms)
        essays_raw = resp_essays.json() if resp_essays.status_code == 200 else []

        tasks_pending = [t for t in tasks_raw if t.get("answer_status") not in ("finished", "submitted")]
        essays_pending = [t for t in essays_raw if t.get("answer_status") not in ("finished", "submitted")]

    return {
        "tasks": tasks_pending,
        "essays": essays_pending
    }

@app.get("/api/task/{task_id}")
async def get_task_detail(task_id: int, user: dict = Depends(get_current_user)):
    fp = _get_browser_context()
    headers_tms = {
        "x-api-key": user["auth_token"],
        "x-api-platform": "webclient",
        "x-api-realm": "edusp",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "User-Agent": fp["user-agent"],
        "sec-ch-ua": fp["sec-ch-ua"],
        "sec-ch-ua-mobile": fp["sec-ch-ua-mobile"],
        "sec-ch-ua-platform": fp["sec-ch-ua-platform"],
    }

    room_name = user.get("room_name", "")
    url_apply = f"{IPTV_BASE_URL}/tms/task/{task_id}/apply?preview_mode=false&token_code=null&room_name={room_name}"

    async with HttpCloakClient(timeout=30.0) as client:
        resp = await tms_apply_with_captcha(client, url_apply, headers_tms, task_id)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"Erro ao abrir tarefa (HTTP {resp.status_code})")

        try:
            task_data = resp.json()
        except Exception:
            task_data = json.loads(base64.b64decode(resp.text).decode("utf-8"))

    _task_cache[task_id] = task_data
    user["apply_times"][task_id] = time.time()
    
    ans_obj = task_data.get("answer")
    if isinstance(ans_obj, dict) and ans_obj.get("id"):
        user["active_answer_ids"][task_id] = ans_obj["id"]

    return task_data

@app.post("/api/ai-fill/{task_id}")
async def ai_fill_task(task_id: int, user: dict = Depends(get_current_user)):
    task_data = _task_cache.get(task_id)
    if not task_data:
        task_data = await get_task_detail(task_id, user=user)

    result = await resolve_task_answers(task_data, task_id)
    return result

@app.post("/api/task/{task_id}/submit")
async def submit_task(task_id: int, req: SubmitRequest, user: dict = Depends(get_current_user)):
    task_data = _task_cache.get(task_id)
    if not task_data:
        task_data = await get_task_detail(task_id, user=user)

    is_essay = task_data.get("is_essay") or task_data.get("task_is_essay") or any(
        q.get("type") == "essay" for q in task_data.get("questions", [])
    )

    answers = req.answers
    for entry in answers.values():
        if isinstance(entry, dict) and entry.get("question_type") == "fill-letters":
            ans_v = entry.get("answer")
            if isinstance(ans_v, list):
                entry["answer"] = "".join(str(x) for x in ans_v)

    apply_time = user.get("apply_times", {}).get(task_id)
    now = time.time()
    if apply_time:
        duration = round(now - apply_time, 2)
    else:
        duration = req.duration or 120.0

    if req.min_time and req.max_time:
        duration = random.uniform(req.min_time * 60, req.max_time * 60)
    elif duration < 60.0:
        duration = 60.0 + random.uniform(5.0, 30.0)

    room_name = user.get("room_name", "")
    answer_id = req.answer_id or user.get("active_answer_ids", {}).get(task_id)

    submit_status = "draft" if is_essay else "submitted"
    submit_payload = {
        "status": submit_status,
        "answers": answers,
        "accessed_on": "room",
        "executed_on": room_name,
        "duration": duration
    }

    fp = _get_browser_context()
    traceparent, request_id = _generate_traceparent()
    headers_submit = {
        "accept": "application/json",
        "accept-language": "pt-BR,pt;q=0.9",
        "content-type": "application/json",
        "origin": "https://saladofuturo.educacao.sp.gov.br",
        "referer": "https://saladofuturo.educacao.sp.gov.br/",
        "request-id": request_id,
        "sec-ch-ua": fp["sec-ch-ua"],
        "sec-ch-ua-mobile": fp["sec-ch-ua-mobile"],
        "sec-ch-ua-platform": fp["sec-ch-ua-platform"],
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "traceparent": traceparent,
        "user-agent": fp["user-agent"],
        "x-api-key": user["auth_token"]
    }

    async with HttpCloakClient(timeout=30.0) as client:
        if is_essay:
            essay_title = ""
            essay_body = ""
            for entry in answers.values():
                if isinstance(entry, dict) and entry.get("question_type") == "essay":
                    ans = entry.get("answer", {})
                    if isinstance(ans, dict):
                        essay_title = ans.get("title", "")
                        essay_body = ans.get("body", "")
                        break
            try:
                check_payload = {"title": essay_title, "body": essay_body}
                await client.post(
                    f"{IPTV_BASE_URL}/tms/task/{task_id}/essay-check",
                    json=check_payload,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                        "origin": "https://saladofuturo.educacao.sp.gov.br",
                        "referer": "https://saladofuturo.educacao.sp.gov.br/",
                        "user-agent": fp["user-agent"],
                        "x-api-key": user["auth_token"]
                    }
                )
            except Exception as e:
                logger.warning(f"essay-check warning: {e}")

        url_apply = f"{IPTV_BASE_URL}/tms/task/{task_id}/apply?preview_mode=false&token_code=null&room_name={room_name}"
        headers_tms = {
            "x-api-key": user["auth_token"],
            "x-api-platform": "webclient",
            "x-api-realm": "edusp",
            "Accept": "application/json",
            "User-Agent": fp["user-agent"],
        }
        apply_resp = await tms_apply_with_captcha(client, url_apply, headers_tms, task_id)
        if apply_resp.status_code == 200:
            try:
                apply_data = apply_resp.json()
                if isinstance(apply_data.get("answer"), dict) and apply_data["answer"].get("id"):
                    answer_id = apply_data["answer"]["id"]
            except Exception:
                pass

        if answer_id:
            url_sub = f"{IPTV_BASE_URL}/tms/task/{task_id}/answer/{answer_id}"
            resp_sub = await client.put(url_sub, json=submit_payload, headers=headers_submit)
        else:
            url_sub = f"{IPTV_BASE_URL}/tms/task/{task_id}/answer"
            resp_sub = await client.post(url_sub, json=submit_payload, headers=headers_submit)

        if resp_sub.status_code != 200:
            raise HTTPException(status_code=resp_sub.status_code, detail=f"Falha no envio: {resp_sub.text[:300]}")

        result_data = resp_sub.json() if resp_sub.text else {}
        user.get("apply_times", {}).pop(task_id, None)

        return {
            "success": True,
            "task_id": task_id,
            "answer_id": result_data.get("id", answer_id),
            "status": result_data.get("status", submit_status),
            "score": result_data.get("result_score"),
            "message": "Enviado com sucesso!" if not is_essay else "Redação salva com sucesso (Rascunho)!"
        }

async def _delayed_worker(job_id: str, task_id: int, req: SubmitRequest, user: dict, delay_seconds: float):
    _delayed_jobs[job_id]["status"] = "waiting"
    _delayed_jobs[job_id]["remaining_seconds"] = delay_seconds
    
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        remaining = max(0, delay_seconds - elapsed)
        _delayed_jobs[job_id]["remaining_seconds"] = round(remaining)
        if remaining <= 0:
            break
        await asyncio.sleep(min(1.0, remaining))

    _delayed_jobs[job_id]["status"] = "submitting"
    try:
        res = await submit_task(task_id, req, user)
        _delayed_jobs[job_id]["status"] = "finished"
        _delayed_jobs[job_id]["result"] = res
    except Exception as e:
        _delayed_jobs[job_id]["status"] = "error"
        _delayed_jobs[job_id]["error"] = str(e)

@app.post("/api/task/{task_id}/submit-delayed")
async def submit_delayed(task_id: int, req: SubmitRequest, user: dict = Depends(get_current_user)):
    job_id = uuid.uuid4().hex
    num_q = len(req.answers)
    
    if req.min_time and req.max_time:
        delay = random.uniform(req.min_time * 60, req.max_time * 60)
    else:
        delay = num_q * 90.0 + random.randint(10, 45)

    _delayed_jobs[job_id] = {
        "job_id": job_id,
        "task_id": task_id,
        "status": "queued",
        "remaining_seconds": round(delay),
        "created_at": time.time()
    }

    asyncio.create_task(_delayed_worker(job_id, task_id, req, user, delay))

    return {
        "success": True,
        "job_id": job_id,
        "remaining_seconds": round(delay),
        "message": f"Envio agendado para daqui a {round(delay / 60, 1)} minutos."
    }

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in _delayed_jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _delayed_jobs[job_id]

async def _solve_single_task_worker(batch_id: str, task_id: int, user: dict, min_time: Optional[float], max_time: Optional[float]):
    batch = _task_batches.get(batch_id)
    if not batch or task_id not in batch["tasks"]:
        return

    task_info = batch["tasks"][task_id]
    task_info["status"] = "resolving_ai"
    task_info["message"] = "Resolvendo questões com IA..."

    try:
        task_data = await get_task_detail(task_id, user=user)
        task_info["title"] = task_data.get("title", task_info.get("title", f"Tarefa #{task_id}"))

        ai_res = await resolve_task_answers(task_data, task_id)
        if not ai_res.get("success") or not ai_res.get("answers"):
            task_info["status"] = "failed"
            task_info["message"] = "IA não gerou respostas para a tarefa."
            return

        answers = ai_res["answers"]
        questions = [q for q in task_data.get("questions", []) if q.get("type") not in ("info", "section")]
        num_q = max(1, len(questions))

        if min_time and max_time:
            delay = random.uniform(min_time * 60, max_time * 60)
        else:
            delay = max(45.0, num_q * 90.0 + random.randint(10, 45))

        task_info["status"] = "waiting_delay"
        task_info["total_seconds"] = round(delay)
        task_info["remaining_seconds"] = round(delay)
        task_info["message"] = f"Aguardando tempo humanizado ({round(delay)}s)..."

        start_time = time.time()
        while True:
            if batch.get("status") == "stopped":
                task_info["status"] = "stopped"
                task_info["message"] = "Execução cancelada pelo usuário."
                return
            elapsed = time.time() - start_time
            rem = max(0, delay - elapsed)
            task_info["remaining_seconds"] = round(rem)
            if rem <= 0:
                break
            await asyncio.sleep(min(1.0, rem))

        if batch.get("status") == "stopped":
            task_info["status"] = "stopped"
            task_info["message"] = "Execução cancelada pelo usuário."
            return

        task_info["status"] = "submitting"
        task_info["message"] = "Enviando respostas..."

        submit_req = SubmitRequest(answers=answers, duration=delay)
        submit_res = await submit_task(task_id, submit_req, user)

        task_info["status"] = "completed"
        task_info["score"] = submit_res.get("score")
        task_info["message"] = submit_res.get("message", "Concluído com sucesso!")

    except Exception as e:
        task_info["status"] = "failed"
        task_info["message"] = f"Erro: {str(e)[:150]}"
    finally:
        completed = sum(1 for t in batch["tasks"].values() if t["status"] in ("completed", "failed", "stopped"))
        batch["completed_count"] = completed
        if completed >= batch["total"] and batch["status"] != "stopped":
            batch["status"] = "completed"

@app.post("/api/tasks/batch-solve")
async def start_tasks_batch_solve(req: TaskBatchSolveRequest, user: dict = Depends(get_current_user)):
    if not req.task_ids:
        raise HTTPException(status_code=400, detail="Nenhuma tarefa selecionada.")

    batch_id = uuid.uuid4().hex
    tasks_map = {
        tid: {
            "id": tid,
            "title": f"Tarefa #{tid}",
            "status": "queued",
            "remaining_seconds": 0,
            "total_seconds": 0,
            "score": None,
            "message": "Aguardando início..."
        }
        for tid in req.task_ids
    }

    batch = {
        "id": batch_id,
        "username": user["username"],
        "total": len(req.task_ids),
        "completed_count": 0,
        "status": "running",
        "created_at": time.time(),
        "tasks": tasks_map
    }
    _task_batches[batch_id] = batch

    for tid in req.task_ids:
        asyncio.create_task(_solve_single_task_worker(batch_id, tid, user, req.min_time, req.max_time))

    return {
        "success": True,
        "batch_id": batch_id,
        "total": len(req.task_ids),
        "message": f"Iniciadas {len(req.task_ids)} tarefas em paralelo com resolução por IA e delay humanizado."
    }

@app.get("/api/tasks/batch/{batch_id}")
async def get_tasks_batch_status(batch_id: str, user: dict = Depends(get_current_user)):
    batch = _task_batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote de tarefas não encontrado.")
    return {"success": True, "batch": batch}

@app.get("/api/tasks/active-batch")
async def get_active_tasks_batch(user: dict = Depends(get_current_user)):
    username = user["username"]
    user_batches = [b for b in _task_batches.values() if b.get("username") == username]
    if not user_batches:
        return {"active": False, "batch": None}
    user_batches.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    active = [b for b in user_batches if b.get("status") in ("running", "queued")]
    if active:
        return {"active": True, "batch": active[0]}
    recent = user_batches[0]
    if time.time() - recent.get("created_at", 0) < 30:
        return {"active": True, "batch": recent}
    return {"active": False, "batch": None}

@app.post("/api/tasks/batch/{batch_id}/stop")
async def stop_tasks_batch(batch_id: str, user: dict = Depends(get_current_user)):
    batch = _task_batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote de tarefas não encontrado.")
    batch["status"] = "stopped"
    return {"success": True, "message": "Lote interrompido com sucesso."}

# ---------------------------------------------------------------------------
# Matific Helpers & Workers
# ---------------------------------------------------------------------------
def get_user_matific_batch_state(username: str):
    if username not in _matific_batches:
        _matific_batches[username] = {
            "status": "idle",
            "current_episode_slug": None,
            "current_episode_title": None,
            "current_progress_percent": 0.0,
            "completed_count": 0,
            "total_count": 0,
            "pending": [],
            "logs": [],
            "current_job_id": None
        }
    return _matific_batches[username]

def generate_matific_timings(min_task_minutes: float, max_task_minutes: float, problem_count: int) -> dict:
    target_duration = random.uniform(min_task_minutes * 60, max_task_minutes * 60)
    fixed_delays = 10.0
    overhead = (problem_count * 1.5) + (max(0, problem_count - 1) * 2.0)
    available_sec = max(20.0, target_duration - fixed_delays - overhead)
    sec_per_question = available_sec / max(1, problem_count)
    standard_avg = 30.0
    scale = max(0.1, min(5.0, sec_per_question / standard_avg))
    return {
        "loading_multiplier": 1.0,
        "solving_min": round(10.0 * scale, 1),
        "solving_max": round(25.0 * scale, 1),
        "struggle_min": round(5.0 * scale, 1),
        "struggle_max": round(15.0 * scale, 1),
        "reading_min": round(2.0 * scale, 1),
        "reading_max": round(6.0 * scale, 1),
        "inter_question_min": round(1.0 * scale, 1),
        "inter_question_max": round(3.0 * scale, 1)
    }

def _invalidate_matific_episodes_cache(username: str):
    if username in _matific_session_cache:
        _matific_session_cache[username]["episodes_assigned"] = None
        _matific_session_cache[username]["episodes_adventure"] = None
        _matific_session_cache[username]["state"] = None

async def _prewarm_matific_session(user: dict):
    try:
        client = await _get_matific_client(user)
        if client:
            try:
                await asyncio.gather(
                    get_matific_episodes("trabalho_atribuido", user),
                    get_matific_episodes("ilha_aventura", user),
                    get_matific_state(user),
                    return_exceptions=True
                )
            finally:
                await client.__aexit__(None, None, None)
    except Exception as e:
        logger.info(f"[MATIFIC-PREWARM] Background note: {e}")

async def _get_matific_client(user: dict) -> Optional[MatificClient]:
    username = user["username"]
    if username not in _matific_locks:
        _matific_locks[username] = asyncio.Lock()

    async with _matific_locks[username]:
        cached = _matific_session_cache.get(username)
        client_obj = MatificClient(
            ra=user["ra"],
            digito=user["digito"],
            uf=user["uf"],
            password=user["password"]
        )
        await client_obj.__aenter__()

        if cached and time.time() < cached["expires_at"]:
            for d in ("www.matific.com", "matific.com", ""):
                client_obj.client.set_cookie("sessionid", cached["sessionid"], domain=d)
                client_obj.client.set_cookie("csrftoken", cached["csrftoken"], domain=d)
                client_obj.client.set_cookie("user_data_token", cached["user_data_token"], domain=d)
                if cached.get("slatemath_user_id"):
                    client_obj.client.set_cookie("slatemath_user_id", cached["slatemath_user_id"], domain=d)
            client_obj.sessionid = cached["sessionid"]
            client_obj.csrftoken = cached["csrftoken"]
            client_obj.user_data_token = cached["user_data_token"]
            client_obj.slatemath_user_id = cached.get("slatemath_user_id")
            client_obj.init_data = cached.get("init_data")
            return client_obj

        auth_ok = await client_obj.authenticate()
        if not auth_ok:
            await client_obj.__aexit__(None, None, None)
            return None

        _matific_session_cache[username] = {
            "sessionid": client_obj.sessionid,
            "csrftoken": client_obj.csrftoken,
            "user_data_token": client_obj.user_data_token,
            "slatemath_user_id": client_obj.slatemath_user_id,
            "expires_at": time.time() + _MATIFIC_SESSION_TTL,
            "init_data": None,
            "episodes_assigned": None,
            "episodes_adventure": None,
            "state": None,
        }
        return client_obj

async def _matific_worker_task(username: str, user: dict, episode: dict, target_accuracy: str, job_id: str, timings: dict = None):
    job = _matific_jobs.get(job_id)
    if not job:
        return
    job["status"] = "running"
    job["logs"].append("Iniciando automação do Matific...")
    client = await _get_matific_client(user)
    if not client:
        job["status"] = "failed"
        job["logs"].append("Erro ao autenticar no Matific. Verifique as credenciais.")
        return

    try:
        job["logs"].append("Autenticação com sucesso! Iniciando simulação do episódio...")
        def on_progress(message, percent):
            if job["status"] == "stopped":
                raise asyncio.CancelledError("Stopped by user")
            job["logs"].append(f"[{percent}%] {message}")
            job["progress_percent"] = percent

        success = await client.complete_episode(episode, target_accuracy=target_accuracy, on_progress=on_progress, timings=timings)
        if success:
            job["status"] = "completed"
            job["logs"].append("Episódio concluído e enviado com sucesso!")
            job["progress_percent"] = 100
            _invalidate_matific_episodes_cache(username)
        else:
            job["status"] = "failed"
            job["logs"].append("O cliente não conseguiu concluir o episódio.")
    except asyncio.CancelledError:
        job["status"] = "stopped"
        job["logs"].append("Simulação interrompida pelo usuário.")
    except Exception as e:
        logger.error(f"[MATIFIC-WORKER] Error: {e}", exc_info=True)
        job["status"] = "failed"
        job["logs"].append(f"Erro na execução: {str(e)}")
    finally:
        await client.__aexit__(None, None, None)

async def _matific_batch_worker(username: str, user: dict, episodes: list, min_time_per_task: float, max_time_per_task: float, min_wait_between: float, max_wait_between: float, target_accuracy: str):
    state = get_user_matific_batch_state(username)
    state["status"] = "running"
    state["total_count"] = len(episodes)
    state["completed_count"] = 0
    state["pending"] = episodes.copy()
    state["logs"] = ["Iniciando lote de tarefas Matific..."]
    state["current_episode_slug"] = None
    state["current_episode_title"] = None
    state["current_progress_percent"] = 0.0
    state["current_job_id"] = None

    try:
        for idx, ep in enumerate(episodes):
            if state["status"] != "running":
                break
            state["current_episode_slug"] = ep.get("slug")
            state["current_episode_title"] = ep.get("title", ep.get("slug"))
            state["current_progress_percent"] = 0.0
            job_id = uuid.uuid4().hex
            state["current_job_id"] = job_id
            _matific_jobs[job_id] = {
                "status": "pending",
                "episode_slug": ep.get("slug"),
                "episode_title": ep.get("title", ep.get("slug")),
                "logs": ["Simulação individual do lote agendada."],
                "progress_percent": 0.0,
                "username": username
            }
            state["logs"].append(f"[{idx+1}/{len(episodes)}] Iniciando: {ep.get('title')}")
            problem_count = ep.get("problem_count", 6) or 6
            timings = generate_matific_timings(min_time_per_task, max_time_per_task, problem_count)
            await _matific_worker_task(username, user, ep, target_accuracy, job_id, timings=timings)

            job_res = _matific_jobs.get(job_id)
            if job_res and job_res["status"] == "completed":
                state["completed_count"] += 1
                state["logs"].append(f"[{idx+1}/{len(episodes)}] Concluído com sucesso: {ep.get('title')}")
            else:
                reason = job_res["logs"][-1] if job_res and job_res["logs"] else "Erro desconhecido"
                state["logs"].append(f"[{idx+1}/{len(episodes)}] Falhou: {ep.get('title')} ({reason})")

            if state["pending"]:
                state["pending"].pop(0)

            if idx < len(episodes) - 1 and state["status"] == "running":
                wait_sec = random.uniform(min_wait_between * 60, max_wait_between * 60)
                state["logs"].append(f"Aguardando {int(wait_sec)}s antes de iniciar a próxima tarefa...")
                sleep_start = time.time()
                while time.time() - sleep_start < wait_sec:
                    if state["status"] != "running":
                        break
                    await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"[MATIFIC-BATCH] Error in batch worker: {e}", exc_info=True)
        state["logs"].append(f"Erro no executor do lote: {str(e)}")
    finally:
        _invalidate_matific_episodes_cache(username)
        state["status"] = "idle"
        state["current_episode_slug"] = None
        state["current_episode_title"] = None
        state["current_progress_percent"] = 0.0
        state["current_job_id"] = None

# ---------------------------------------------------------------------------
# Matific Routes
# ---------------------------------------------------------------------------
@app.get("/api/matific/episodes")
async def get_matific_episodes(source: str = "trabalho_atribuido", user: dict = Depends(get_current_user)):
    username = user["username"]
    cached_session = _matific_session_cache.get(username)
    cache_key = "episodes_assigned" if source == "trabalho_atribuido" else "episodes_adventure"
    if cached_session and cached_session.get(cache_key):
        ts, cached_list = cached_session[cache_key]
        if time.time() - ts < _MATIFIC_EPISODES_TTL and cached_list:
            return {"success": True, "episodes": cached_list, "source": source, "cached": True}

    client = await _get_matific_client(user)
    if not client:
        raise HTTPException(status_code=401, detail="Falha na autenticação do Matific via SSO")

    try:
        init_data = getattr(client, "init_data", None)
        if not init_data:
            init_data = await client.get_init_data()
            if init_data and username in _matific_session_cache:
                _matific_session_cache[username]["init_data"] = init_data

        if not init_data:
            raise HTTPException(status_code=502, detail="Falha ao obter dados de inicialização do Matific")

        episodes_list = []
        campaigns = init_data.get("Campaigns", [])
        campaign_ids = [c.get("Id") for c in campaigns if c.get("Id")]
        default_campaign_id = campaign_ids[0] if campaign_ids else None

        if source == "ilha_aventura":
            enrichment = await client.get_episode_enrichment()
            game_state = await client.fetch_game_state(campaign_ids=campaign_ids or [])
            played_episodes = _aggregate_played_episodes(game_state)

            road_seen = set()
            for ent in game_state.get("game_entity", []):
                if ent.get("object_type") != "Matific.Mad.EpisodeStorableData":
                    continue
                ent_id = ent.get("entity_id")
                if ent_id in road_seen:
                    continue
                road_seen.add(ent_id)
                agg = played_episodes.get(ent_id)
                if agg and agg.get("was_passed"):
                    continue

                assigned_ids = set()
                for c in campaigns:
                    for ep in c.get("Episodes", []):
                        assigned_ids.add(ep.get("EpisodeId"))
                for key in ["School", "Home", "Parent"]:
                    for ass in init_data.get("Assignments", {}).get(key, []):
                        assigned_ids.add(ass.get("EpisodeId"))
                if ent_id in assigned_ids:
                    continue

                meta = enrichment.get(ent_id, {})
                slug = meta.get("Slug")
                if not slug:
                    continue

                title = meta.get("Title") or translate_matific_slug(slug)
                subtitle = meta.get("Subtitle", "")

                ep_data = {
                    "slug": slug,
                    "assignment_id": ent.get("instance_id") or ent.get("row_id"),
                    "campaign_id": default_campaign_id,
                    "context_id": 13,
                    "due_date": None,
                    "source": "Ilha da Aventura",
                    "episode_id": ent_id,
                    "title": title,
                    "subtitle": subtitle,
                    "problem_count": 6,
                    "completed": False,
                    "highest_score": ent.get("highest_score"),
                    "was_passed": False,
                    "zone": ent.get("zone"),
                    "order": ent.get("order")
                }
                episodes_list.append(ep_data)

            episodes_list.sort(key=lambda x: (x.get("zone") or 0, x.get("order") or 0))
            if username in _matific_session_cache:
                _matific_session_cache[username]["episodes_adventure"] = (time.time(), episodes_list)
            return {"success": True, "episodes": episodes_list, "source": source}

        played_episodes = {}
        if campaign_ids:
            try:
                game_state = await client.fetch_game_state(campaign_ids=campaign_ids)
                played_episodes = _aggregate_played_episodes(game_state)
            except Exception as ex:
                logger.error(f"[MATIFIC-EPISODES] Game state error: {ex}")

        for campaign in campaigns:
            campaign_id = campaign.get("Id")
            campaign_name = campaign.get("TranslatedName") or campaign.get("Name") or "Campanha Ativa"
            context_id = campaign.get("NewContext", 13)
            for ep in campaign.get("Episodes", []):
                episode_id = ep.get("EpisodeId")
                pe = played_episodes.get(episode_id)
                slug = ep.get("Slug")
                title = translate_matific_slug(slug)
                ep_data = {
                    "slug": slug,
                    "assignment_id": ep.get("AssignmentId"),
                    "campaign_id": campaign_id,
                    "context_id": context_id,
                    "due_date": ep.get("DueDate"),
                    "source": f"Campanha: {campaign_name}",
                    "episode_id": episode_id,
                    "title": title,
                    "subtitle": "",
                    "problem_count": 6,
                    "completed": pe is not None and (pe.get("was_passed") or pe.get("highest_score") is not None),
                    "highest_score": pe["highest_score"] if pe else None,
                    "was_passed": pe["was_passed"] if pe else False
                }
                episodes_list.append(ep_data)

        for key in ["School", "Home", "Parent"]:
            for ass in init_data.get("Assignments", {}).get(key, []):
                episode_id = ass.get("Id") or ass.get("EpisodeId")
                pe = played_episodes.get(episode_id)
                slug = ass.get("Slug") or ass.get("EpisodeSlug")
                title = translate_matific_slug(slug)
                ep_data = {
                    "slug": slug,
                    "assignment_id": ass.get("AssignmentId"),
                    "campaign_id": ass.get("CampaignId") or default_campaign_id,
                    "context_id": ass.get("ContextId", 13),
                    "due_date": ass.get("DueDate"),
                    "source": f"Atribuição: {key}",
                    "episode_id": episode_id,
                    "title": title,
                    "subtitle": "",
                    "problem_count": 6,
                    "completed": pe is not None and (pe.get("was_passed") or pe.get("highest_score") is not None),
                    "highest_score": pe["highest_score"] if pe else None,
                    "was_passed": pe["was_passed"] if pe else False
                }
                episodes_list.append(ep_data)

        if username in _matific_session_cache:
            _matific_session_cache[username]["episodes_assigned"] = (time.time(), episodes_list)
        return {"success": True, "episodes": episodes_list, "source": source}
    finally:
        await client.__aexit__(None, None, None)

@app.post("/api/matific/complete")
async def start_matific_simulation(req: MatificCompleteRequest, user: dict = Depends(get_current_user)):
    episode = req.episode
    if not episode or not episode.get("slug"):
        raise HTTPException(status_code=400, detail="Detalhes do episódio inválidos")

    username = user["username"]
    batch_state = get_user_matific_batch_state(username)
    if batch_state["status"] == "running":
        raise HTTPException(status_code=400, detail="Existe um lote do Matific em execução. Aguarde ou cancele o lote.")

    for j in _matific_jobs.values():
        if j["username"] == username and j["status"] in ("pending", "running"):
            raise HTTPException(status_code=400, detail="Já existe uma simulação em andamento para esta conta.")

    job_id = uuid.uuid4().hex
    _matific_jobs[job_id] = {
        "status": "pending",
        "episode_slug": episode.get("slug"),
        "episode_title": episode.get("title", episode.get("slug")),
        "logs": ["Simulação de episódio agendada."],
        "progress_percent": 0.0,
        "username": username
    }
    asyncio.create_task(_matific_worker_task(username, user, episode, req.target_accuracy or "realistic", job_id, timings=req.timings))
    return {"success": True, "job_id": job_id}

@app.get("/api/matific/job/{job_id}")
async def get_matific_job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = _matific_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["username"] != user["username"]:
        raise HTTPException(status_code=403, detail="Não autorizado")
    return job

@app.post("/api/matific/job/{job_id}/stop")
async def stop_matific_job(job_id: str, user: dict = Depends(get_current_user)):
    job = _matific_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["username"] != user["username"]:
        raise HTTPException(status_code=403, detail="Não autorizado")
    job["status"] = "stopped"
    return {"success": True}

@app.post("/api/matific/batch")
async def start_matific_batch(req: MatificBatchRequest, user: dict = Depends(get_current_user)):
    if not req.episodes:
        raise HTTPException(status_code=400, detail="Lista de episódios vazia")

    username = user["username"]
    state = get_user_matific_batch_state(username)
    if state["status"] == "running":
        raise HTTPException(status_code=400, detail="Já existe um lote em execução")

    for j in _matific_jobs.values():
        if j["username"] == username and j["status"] in ("pending", "running"):
            raise HTTPException(status_code=400, detail="Existe uma simulação individual em execução. Aguarde a conclusão.")

    asyncio.create_task(_matific_batch_worker(
        username, user, req.episodes,
        req.min_time_per_task or 1.0, req.max_time_per_task or 3.0,
        req.min_wait_between or 0.2, req.max_wait_between or 1.0,
        req.target_accuracy or "realistic"
    ))
    return {"success": True}

@app.get("/api/matific/batch/status")
async def get_matific_batch_status(user: dict = Depends(get_current_user)):
    username = user["username"]
    state = get_user_matific_batch_state(username)
    response_data = state.copy()
    if state["status"] == "running" and state["current_job_id"]:
        job = _matific_jobs.get(state["current_job_id"])
        if job:
            response_data["current_progress_percent"] = job.get("progress_percent", 0.0)
            response_data["active_job_logs"] = job.get("logs", [])[-5:]
    return response_data

@app.post("/api/matific/batch/stop")
async def stop_matific_batch(user: dict = Depends(get_current_user)):
    username = user["username"]
    state = get_user_matific_batch_state(username)
    if state["status"] == "running":
        state["status"] = "stopped"
        state["logs"].append("Lote interrompido pelo usuário.")
        if state["current_job_id"]:
            job = _matific_jobs.get(state["current_job_id"])
            if job:
                job["status"] = "stopped"
                job["logs"].append("Cancelado pelo cancelamento do lote.")
    return {"success": True}

@app.get("/api/matific/state")
async def get_matific_state(user: dict = Depends(get_current_user)):
    username = user["username"]
    cached_session = _matific_session_cache.get(username)
    if cached_session and cached_session.get("state"):
        ts, cached_state = cached_session["state"]
        if time.time() - ts < _MATIFIC_STATE_TTL and cached_state:
            return {"success": True, "state": cached_state, "cached": True}

    client = await _get_matific_client(user)
    if not client:
        raise HTTPException(status_code=401, detail="Falha na autenticação do Matific via SSO")

    try:
        init_data = getattr(client, "init_data", None)
        if not init_data:
            init_data = await client.get_init_data()
            if init_data and username in _matific_session_cache:
                _matific_session_cache[username]["init_data"] = init_data

        if not init_data:
            raise HTTPException(status_code=502, detail="Falha ao obter dados de inicialização do Matific")

        campaigns = init_data.get("Campaigns", [])
        campaign_id = campaigns[0].get("Id") if campaigns else None
        if not campaign_id:
            for key in ["School", "Home", "Parent"]:
                asses = init_data.get("Assignments", {}).get(key, [])
                if asses:
                    campaign_id = asses[0].get("CampaignId")
                    break

        if not campaign_id:
            campaign_id = "default_campaign"

        state = await client.fetch_inventory_and_customization(campaign_id)
        result_state = {
            "coins": state["coins"],
            "xp": state["xp"],
            "rank": state["rank"],
            "weekly_goal": state["weekly_goal"],
            "weekly_goal_target": state["weekly_goal_target"],
            "inventory": state["inventory"],
            "customization": state["customization"],
            "campaign_id": campaign_id
        }
        if username in _matific_session_cache:
            _matific_session_cache[username]["state"] = (time.time(), result_state)
        return {
            "success": True,
            "state": result_state
        }
    finally:
        await client.__aexit__(None, None, None)

@app.post("/api/matific/purchase")
async def purchase_matific_item(req: MatificPurchaseRequest, user: dict = Depends(get_current_user)):
    username = user["username"]
    client = await _get_matific_client(user)
    if not client:
        raise HTTPException(status_code=401, detail="Falha na autenticação do Matific via SSO")
    try:
        success = await client.purchase_item(req.campaign_id, req.item_id, req.cost)
        if not success:
            raise HTTPException(status_code=400, detail="Falha ao comprar o item. Saldo insuficiente ou erro no servidor.")
        _invalidate_matific_episodes_cache(username)
        return {"success": True, "message": "Item comprado com sucesso!"}
    finally:
        await client.__aexit__(None, None, None)

@app.post("/api/matific/equip")
async def equip_matific_item(req: MatificEquipRequest, user: dict = Depends(get_current_user)):
    username = user["username"]
    client = await _get_matific_client(user)
    if not client:
        raise HTTPException(status_code=401, detail="Falha na autenticação do Matific via SSO")
    try:
        success = await client.equip_item(req.campaign_id, req.part_name, req.item_id)
        if not success:
            raise HTTPException(status_code=400, detail="Falha ao equipar o item.")
        _invalidate_matific_episodes_cache(username)
        return {"success": True, "message": "Item equipado com sucesso!"}
    finally:
        await client.__aexit__(None, None, None)

@app.post("/api/matific/repair-customization")
async def repair_matific_customization(req: MatificRepairRequest, user: dict = Depends(get_current_user)):
    username = user["username"]
    client = await _get_matific_client(user)
    if not client:
        raise HTTPException(status_code=401, detail="Falha na autenticação do Matific via SSO")
    try:
        res = await client.repair_customization(req.campaign_id)
        _invalidate_matific_episodes_cache(username)
        return res
    finally:
        await client.__aexit__(None, None, None)

@app.post("/api/matific/set_stats")
async def set_matific_stats(req: MatificSetStatsRequest, user: dict = Depends(get_current_user)):
    username = user["username"]
    client = await _get_matific_client(user)
    if not client:
        raise HTTPException(status_code=401, detail="Falha na autenticação do Matific via SSO")
    try:
        success = await client.set_stats(req.campaign_id, coins=req.coins, xp=req.xp, rank=req.rank)
        if not success:
            raise HTTPException(status_code=502, detail="Falha ao atualizar estatísticas no Matific.")
        _invalidate_matific_episodes_cache(username)
        return {"success": True, "message": "Estatísticas atualizadas com sucesso!"}
    finally:
        await client.__aexit__(None, None, None)


class LeiaSPReadRequest(BaseModel):
    book_id: Optional[int] = None
    pages_to_read: Optional[int] = 0
    min_time: Optional[int] = 20
    max_time: Optional[int] = 40
    auto_solve_quiz: Optional[bool] = True
    sequential: Optional[bool] = False

async def _get_leiasp_client(user: dict) -> LeiaSPClient:
    token_sed = user.get("token_sed")
    leiasp_jwt = user.get("leiasp_jwt")
    if not token_sed and not leiasp_jwt:
        raise HTTPException(status_code=401, detail="Sessão SED inválida ou expirada.")
    client = LeiaSPClient(token_sed=token_sed, leiasp_jwt=leiasp_jwt)
    try:
        await client.authenticate()
        return client
    except Exception as e:
        logger.error(f"[LeiaSP] Erro ao autenticar no Elefante Letrado: {e}")
        raise HTTPException(status_code=502, detail=f"Erro ao autenticar no LeiaSP/Elefante Letrado: {e}")

async def _wait_job(job: dict, seconds: int = 0) -> bool:
    for _ in range(max(1, seconds)):
        while job.get("status") == "paused":
            await asyncio.sleep(0.5)
            if job.get("status") == "stopped":
                return False
        if job.get("status") == "stopped":
            return False
        if seconds > 0:
            await asyncio.sleep(1)
    return job.get("status") != "stopped"

async def _read_single_leiasp_book_core(
    client: LeiaSPClient,
    book_id: int,
    pages_to_read: int,
    min_time: int,
    max_time: int,
    auto_solve_quiz: bool,
    job: dict
) -> bool:
    job["logs"].append(f"Obtendo metadados do livro ID {book_id}...")
    try:
        meta = await client.get_book_metadata(book_id)
    except Exception as e:
        job["logs"].append(f"Erro ao buscar metadados do livro {book_id}: {e}")
        return False

    book_title = meta.get("BookTitle") or meta.get("Title") or f"Livro #{book_id}"
    cover_path = meta.get("CoverPageUrl") or meta.get("ThumbnailCoverPic") or meta.get("CoverUrl") or meta.get("CoverThumbnailUrl") or meta.get("UrlToCoverImage") or ""
    if cover_path.startswith("/"):
        cover_path = f"{client.ELEFANTE_CDN_BASE}{cover_path}"

    job["book_id"] = book_id
    job["book_title"] = book_title
    job["book_cover_url"] = cover_path

    book_context = {
        "title": book_title,
        "authors": meta.get("Authors") or meta.get("Author") or "",
        "publisher": meta.get("Publisher") or "",
        "synopsis": meta.get("Synopsis") or meta.get("Description") or "",
        "isbn": meta.get("Isbn") or "",
    }

    is_quiz_active = bool(meta.get("IsQuizActive"))
    total_pages = meta.get("NumberPages") or 100
    current_page = 1

    reading_info = meta.get("Reading")
    if isinstance(reading_info, list):
        for r in reading_info:
            if r.get("Type") == "Read":
                current_page = r.get("Page") or 1
                break

    epub_url_path = meta.get("UrlToEpubFile", "")
    epub_url = f"{client.ELEFANTE_CDN_BASE}{epub_url_path}" if epub_url_path.startswith("/") else epub_url_path

    page_cfi_map = []
    epub_hash = ""
    if epub_url:
        job["logs"].append("Baixando EPUB para mapear spine e calcular CFIs Colibrio...")
        epub_hash, page_cfi_map = await client.parse_epub(epub_url, total_pages)
        if page_cfi_map:
            job["logs"].append(f"Mapa CFI construído com sucesso: {len(page_cfi_map)} páginas mapeadas.")

    job["total_pages"] = total_pages
    job["current_page"] = current_page
    job["logs"].append(f"Iniciando: '{book_title}' | Páginas: {total_pages} | Página atual: {current_page}")

    pages_to_read_actual = pages_to_read if pages_to_read > 0 else (total_pages - current_page + 1)
    target_page = min(total_pages, current_page + pages_to_read_actual - 1)

    if current_page <= target_page and current_page < total_pages:
        if epub_url:
            await client.simulate_colibrio_epub_load(epub_url, job)
        await client.start_session(book_id)

        pages_read_count = 0
        for page in range(current_page, target_page + 1):
            read_time = random.randint(min_time, max_time)
            job["logs"].append(f"Lendo página {page}/{total_pages} por {read_time}s...")

            if not await _wait_job(job, read_time):
                job["logs"].append("Leitura interrompida pelo usuário.")
                return False

            if page_cfi_map and page <= len(page_cfi_map):
                cfi_value = page_cfi_map[page - 1]
            else:
                spine_item = (page * 2) + 2
                h = epub_hash or "0000000000000000000000000000000000000000"
                cfi_value = f"com.colibrio.epub.signature:{h}#epubcfi(/6/{spine_item}!/4/1:0)"

            is_final_page = (page == target_page and page >= total_pages)
            try:
                if is_final_page:
                    finish_res = await client.finish_book(book_id, total_pages, cfi_value, read_time)
                    prog = finish_res.get("progress", {})
                    if prog.get("success"):
                        is_ok = finish_res.get("is_completed_with_success")
                        pts = finish_res.get("points", 0)
                        job["logs"].append(f"Livro finalizado na API LeiaSP! {'(Sucesso total)' if is_ok else '(Tempo registrado)'} | Pontos: {pts}")
                    else:
                        job["logs"].append(f"Aviso ao finalizar livro: {prog.get('error', 'Sem resposta')}")
                else:
                    prog_res = await client.send_page_progress(book_id, page, total_pages, cfi_value, read_time)
                    if prog_res.get("success"):
                        job["logs"].append(f"Página {page}/{total_pages} registrada com sucesso.")
                    else:
                        job["logs"].append(f"Aviso no registro da página {page}: {prog_res.get('error', 'Falha')}")
            except Exception as e:
                job["logs"].append(f"Erro ao registrar página {page}: {e}")

            pages_read_count += 1
            job["current_page"] = page
            job["progress_percent"] = round((pages_read_count / max(pages_to_read_actual, 1)) * 100, 1)

            if not is_final_page and ((pages_read_count % 10 == 0) or (page == target_page)):
                try:
                    close_res = await client.close_book_checkpoint(book_id, read_time)
                    if close_res:
                        job["logs"].append(f"Checkpoint intermediário salvo (pág {page})")
                except Exception as e:
                    job["logs"].append(f"Aviso no checkpoint: {e}")

    if auto_solve_quiz and is_quiz_active and job.get("status") != "stopped":
        job["logs"].append("Verificando questionário do livro...")
        try:
            quiz_data = await client.fetch_quiz(book_id)
            if quiz_data.get("QuizEnabled") and not quiz_data.get("QuizComplete"):
                questions = quiz_data.get("Question", [])
                if questions:
                    job["logs"].append(f"Quiz ativo com {len(questions)} questões. Resolvendo...")
                    q_answers = {}
                    for idx, q in enumerate(questions):
                        if job.get("status") == "stopped":
                            break
                        q_id = q.get("Id")
                        q_type = q.get("QuestionTypeId")
                        q_text = q.get("Text", "")

                        cached = get_cached_leiasp_quiz_answer(book_id, q_id)
                        if cached:
                            job["logs"].append(f"Questão {idx+1}: resposta do cache SQLite.")
                            if q_type != 10:
                                q_answers[q_id] = {"Id": int(q_id), "Answers": cached if isinstance(cached, list) else [cached], "TrueFalseCorrect": True}
                            else:
                                q_answers[q_id] = {
                                    "Id": int(q_id), "Answers": [], "TrueFalseCorrect": True,
                                    "DissertativeResponse": str(cached), "DissertativeEvaluation": "correta",
                                    "DissertativeEvaluationResult": "correta", "DissertativeStudentFeedback": "",
                                    "DissertativeJsonTextFormEvaluation": "{}", "DissertativeElephantTips": ""
                                }
                            continue

                        if q_type != 10:
                            correct_ids = [int(ans.get("Id")) for ans in q.get("Answer", []) if ans.get("IsCorrectAnswer")]
                            if not correct_ids:
                                job["logs"].append(f"Questão {idx+1}: consultando IA...")
                                correct_ids = await resolve_leiasp_objective(q, book_context)
                                if not correct_ids and q.get("Answer"):
                                    correct_ids = [int(q["Answer"][0].get("Id"))]
                            save_cached_leiasp_quiz_answer(book_id, q_id, q_text, "objective", q.get("Answer", []), correct_ids)
                            q_answers[q_id] = {"Id": int(q_id), "Answers": correct_ids, "TrueFalseCorrect": True}
                        else:
                            job["logs"].append(f"Questão {idx+1} (Dissertativa): gerando resposta com IA...")
                            student_resp = await resolve_leiasp_dissertative(q_text, book_context)
                            eval_data = {}
                            try:
                                eval_data = await client.evaluate_dissertative_answer(book_id, int(q_id), q_text, student_resp)
                            except Exception:
                                pass
                            save_cached_leiasp_quiz_answer(book_id, q_id, q_text, "dissertative", [], student_resp)
                            q_answers[q_id] = {
                                "Id": int(q_id), "Answers": [], "TrueFalseCorrect": True,
                                "DissertativeResponse": student_resp,
                                "DissertativeEvaluation": eval_data.get("EvaluationResult") or "correta",
                                "DissertativeEvaluationResult": eval_data.get("EvaluationResult") or "correta",
                                "DissertativeStudentFeedback": eval_data.get("StudentFeedback") or "",
                                "DissertativeJsonTextFormEvaluation": eval_data.get("JsonTextFormEvaluation") or "{}",
                                "DissertativeElephantTips": eval_data.get("ElephantTips") or ""
                            }

                    by_milestone = {}
                    for q in questions:
                        by_milestone.setdefault(q.get("MilestonePercentage"), []).append(q)

                    for m in sorted(by_milestone.keys(), key=lambda x: (x is None, x or 0)):
                        if job.get("status") == "stopped":
                            break
                        g_answers = [q_answers[q.get("Id")] for q in by_milestone[m] if q.get("Id") in q_answers]
                        if g_answers:
                            res_m = await client.submit_milestone_quiz(book_id, m, g_answers)
                            approved = res_m.get("Approved", False) if isinstance(res_m, dict) else False
                            job["logs"].append(f"Milestone {m}% enviado | Aprovado={approved}")

                    if job.get("status") != "stopped":
                        await client.finish_quiz(book_id)
                        job["logs"].append("Quiz do livro concluído!")
            else:
                job["logs"].append("Nenhum quiz pendente para este livro.")
        except Exception as e:
            job["logs"].append(f"Aviso durante verificação de quiz: {e}")

    job["logs"].append(f"Livro '{book_title}' finalizado com sucesso!")
    return True

async def _leiasp_reader_worker(
    session_data: dict,
    book_id: Optional[int],
    pages_to_read: int,
    min_time: int,
    max_time: int,
    auto_solve_quiz: bool,
    sequential: bool,
    job_id: str
):
    job = _leiasp_jobs.get(job_id)
    if not job:
        return

    job["status"] = "running"
    job["logs"].append("Iniciando sessão do LeiaSP...")

    client = LeiaSPClient(token_sed=session_data.get("token_sed"), leiasp_jwt=session_data.get("leiasp_jwt"))
    try:
        await client.authenticate()
        job["logs"].append("Autenticado com sucesso no Elefante Letrado!")

        if not sequential and book_id:
            await _read_single_leiasp_book_core(
                client=client, book_id=book_id, pages_to_read=pages_to_read,
                min_time=min_time, max_time=max_time, auto_solve_quiz=auto_solve_quiz, job=job
            )
        else:
            job["logs"].append("Modo Sequencial: obtendo catálogo de livros incompletos...")
            books = await client.get_library_books()
            incomplete = [b for b in books if not b.get("is_complete") and b.get("progress", 0) < 100.0]

            if not incomplete:
                job["logs"].append("Nenhum livro incompleto encontrado na biblioteca.")
            else:
                job["queue_total"] = len(incomplete)
                job["queue_completed"] = []
                job["logs"].append(f"Encontrados {len(incomplete)} livros incompletos. Iniciando fila...")
                for idx, b in enumerate(incomplete):
                    if not await _wait_job(job):
                        job["logs"].append("Fila sequencial interrompida pelo usuário.")
                        break

                    job["queue_current_idx"] = idx + 1
                    job["queue_current_title"] = b.get("title")
                    job["logs"].append(f"\n--- [Livro {idx+1}/{len(incomplete)}] {b.get('title')} ---")
                    await _read_single_leiasp_book_core(
                        client=client, book_id=b["id"], pages_to_read=0,
                        min_time=min_time, max_time=max_time, auto_solve_quiz=auto_solve_quiz, job=job
                    )
                    job["queue_completed"].append(b.get("title"))

                    if idx + 1 < len(incomplete) and job["status"] not in ("stopped", "paused"):
                        pause_sec = random.randint(15, 30)
                        job["logs"].append(f"Pausa humanizada de {pause_sec}s entre livros...")
                        if not await _wait_job(job, pause_sec):
                            break

        if job["status"] not in ("stopped", "failed"):
            job["status"] = "completed"
            job["progress_percent"] = 100.0
            job["logs"].append("Todas as operações do LeiaSP foram concluídas com sucesso!")

    except Exception as e:
        logger.error(f"[LeiaSP Worker] Erro no worker: {e}", exc_info=True)
        job["status"] = "failed"
        job["logs"].append(f"Erro durante a execução: {e}")
    finally:
        await client.client.aclose()

@app.get("/api/leiasp/books")
async def get_leiasp_books_endpoint(user: dict = Depends(get_current_user)):
    client = await _get_leiasp_client(user)
    try:
        books = await client.get_library_books()
        return {"success": True, "books": books, "total": len(books)}
    finally:
        await client.client.aclose()

@app.get("/api/leiasp/active-job")
async def get_active_leiasp_job_endpoint(user: dict = Depends(get_current_user)):
    username = user["username"]
    user_jobs = [j for j in _leiasp_jobs.values() if j.get("username") == username]
    if not user_jobs:
        return {"active": False, "job": None}

    user_jobs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    active = [j for j in user_jobs if j.get("status") in ("running", "paused", "pending")]
    if active:
        return {"active": True, "job": active[0]}

    recent = user_jobs[0]
    if time.time() - recent.get("created_at", 0) < 45:
        return {"active": True, "job": recent}

    return {"active": False, "job": None}

@app.post("/api/leiasp/read")
async def start_leiasp_reading_endpoint(req: LeiaSPReadRequest, user: dict = Depends(get_current_user)):
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "username": user["username"],
        "book_id": req.book_id,
        "book_title": "Carregando...",
        "book_cover_url": "",
        "sequential": req.sequential,
        "queue_total": 0,
        "queue_current_idx": 0,
        "queue_current_title": "",
        "queue_completed": [],
        "status": "pending",
        "progress_percent": 0.0,
        "current_page": 0,
        "total_pages": 0,
        "logs": ["Job criado. Aguardando inicialização..."],
        "created_at": time.time(),
    }
    _leiasp_jobs[job_id] = job

    min_t = max(10, req.min_time or 20)
    max_t = max(min_t, req.max_time or 40)

    asyncio.create_task(
        _leiasp_reader_worker(
            session_data=user,
            book_id=req.book_id,
            pages_to_read=req.pages_to_read or 0,
            min_time=min_t,
            max_time=max_t,
            auto_solve_quiz=bool(req.auto_solve_quiz),
            sequential=bool(req.sequential),
            job_id=job_id
        )
    )

    return {"success": True, "job_id": job_id, "message": "Leitura iniciada com sucesso em background."}

@app.get("/api/leiasp/job/{job_id}")
async def get_leiasp_job_status_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = _leiasp_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de leitura não encontrado.")
    return {"success": True, "job": job}

@app.post("/api/leiasp/job/{job_id}/pause")
async def pause_leiasp_job_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = _leiasp_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de leitura não encontrado.")
    if job.get("status") == "running":
        job["status"] = "paused"
        job["logs"].append("⏸️ Leitura pausada pelo usuário.")
    return {"success": True, "message": "Job pausado com sucesso.", "job": job}

@app.post("/api/leiasp/job/{job_id}/resume")
async def resume_leiasp_job_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = _leiasp_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de leitura não encontrado.")
    if job.get("status") == "paused":
        job["status"] = "running"
        job["logs"].append("▶️ Leitura retomada pelo usuário.")
    return {"success": True, "message": "Job retomado com sucesso.", "job": job}

@app.post("/api/leiasp/job/{job_id}/stop")
async def stop_leiasp_job_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = _leiasp_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de leitura não encontrado.")
    job["status"] = "stopped"
    job["logs"].append("⏹️ Comando de parada recebido do usuário.")
    return {"success": True, "message": "Job interrompido com sucesso.", "job": job}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)

