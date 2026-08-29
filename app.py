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
from database import init_db
from ai_solver import resolve_task_answers
from matific_client import (
    MatificClient,
    translate_matific_slug,
    _aggregate_played_episodes
)

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
            "auth_token": auth_token,
            "nick": nick,
            "room_name": "",
            "apply_times": {}, # task_id -> timestamp
            "active_answer_ids": {}, # task_id -> answer_id
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
