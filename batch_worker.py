import asyncio
import os
import sys
import json
import time
import random
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
from ai_solver import resolve_task_answers
from database import init_db

LOG_FILE = os.environ.get("BATCH_LOG_FILE", os.path.join(BASE_DIR, "batch_execution.log"))
STATUS_FILE = os.environ.get("BATCH_STATUS_FILE", os.path.join(BASE_DIR, "batch_status.json"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("batch_worker")

def write_status(state: dict):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao gravar status: {e}")

async def run_batch(ra=None, password=None, delay_minutes=20.0):
    if not ra or not password:
        raise SystemExit(
            "Informe RA e senha via argumentos ou env (SALADOPASSADO_RA / SALADOPASSADO_PASSWORD). "
            "Nunca commite credenciais reais."
        )
    init_db()
    
    ra_part = ra.split("-")[0].replace(" ", "").lstrip("0")
    rest = ra.split("-")[1].strip().split()
    digito = rest[0]
    uf = rest[1].upper() if len(rest) > 1 else "SP"
    constructed_user = f"{ra_part}{digito}{uf}"
    
    logger.info(f"Iniciando automação para RA {constructed_user} com delay de {delay_minutes} minutos.")
    
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
    
    async with HttpCloakClient(timeout=30.0) as client:
        # 1. Login SED
        resp_sed = await client.post(
            SED_LOGIN_URL,
            json={"user": constructed_user, "senha": password},
            headers=headers_login
        )
        if resp_sed.status_code != 200:
            logger.error(f"Falha no login SED: {resp_sed.text}")
            return
        
        data_sed = resp_sed.json()
        token_sed = data_sed.get("token")
        user_info = data_sed.get("DadosUsuario", {})
        student_name = user_info.get("NAME") or user_info.get("Nome") or "Estudante"
        logger.info(f"Aluno autenticado: {student_name}")
        
        headers_valida = dict(headers_login)
        headers_valida["Authorization"] = f"Bearer {token_sed}"
        await client.post(SED_VALIDA_URL, headers=headers_valida)
        
        # 2. Login IPTV
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
        iptv_data = resp_iptv.json()
        auth_token = iptv_data.get("auth_token")
        nick = iptv_data.get("nick")
        
        # 3. List Rooms and Pending Tasks
        headers_tms = {
            "x-api-key": auth_token,
            "x-api-platform": "webclient",
            "x-api-realm": "edusp",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "User-Agent": fp["user-agent"],
            "sec-ch-ua": fp["sec-ch-ua"],
            "sec-ch-ua-mobile": fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": fp["sec-ch-ua-platform"],
        }
        
        url_rooms = f"{IPTV_BASE_URL}/room/user?list_all=true&with_cards=true"
        resp_rooms = await client.get(url_rooms, headers=headers_tms)
        rooms = resp_rooms.json().get("rooms", []) if resp_rooms.status_code == 200 else []
        room_name = rooms[0].get("name", "") if rooms else ""
        
        targets = []
        for r in rooms:
            rname = r.get("name")
            if rname:
                targets.append(f"publication_target={rname}")
                targets.append(f"publication_target={rname}:{nick}")
            for cat in r.get("group_categories", []):
                cid = cat.get("id")
                if cid:
                    targets.append(f"publication_target={cid}")
        targets_query = "&".join(targets)
        
        url_tasks = f"{IPTV_BASE_URL}/tms/task/todo?expired_only=false&limit=100&offset=0&filter_expired=true&is_exam=false&with_answer=true&is_essay=false&{targets_query}&with_apply_moment=true"
        resp_tasks = await client.get(url_tasks, headers=headers_tms)
        tasks_raw = resp_tasks.json() if resp_tasks.status_code == 200 else []
        
        pending_tasks = [t for t in tasks_raw if t.get("answer_status") not in ("finished", "submitted")]
        logger.info(f"Encontradas {len(pending_tasks)} tarefas pendentes.")
        
        state = {
            "student": student_name,
            "ra": constructed_user,
            "total_tasks": len(pending_tasks),
            "completed": 0,
            "delay_minutes": delay_minutes,
            "start_time": time.time(),
            "status": "running",
            "tasks": {}
        }
        
        for t in pending_tasks:
            tid = t.get("id")
            state["tasks"][str(tid)] = {
                "id": tid,
                "title": t.get("title"),
                "status": "pending",
                "score": None,
                "message": "Aguardando processamento"
            }
        write_status(state)
        
        # Function to process one task
        async def process_task(task_item):
            tid = task_item.get("id")
            title = task_item.get("title")
            task_state = state["tasks"][str(tid)]
            
            try:
                logger.info(f"[{tid}] Abrindo e resolvendo com IA: {title}")
                task_state["status"] = "resolving_ai"
                task_state["message"] = "Resolvendo com IA..."
                write_status(state)
                
                url_apply = f"{IPTV_BASE_URL}/tms/task/{tid}/apply?preview_mode=false&token_code=null&room_name={room_name}"
                apply_resp = await tms_apply_with_captcha(client, url_apply, headers_tms, tid)
                if apply_resp.status_code != 200:
                    raise Exception(f"Erro ao abrir tarefa: HTTP {apply_resp.status_code}")
                
                task_data = apply_resp.json()
                answer_id = None
                if isinstance(task_data.get("answer"), dict) and task_data["answer"].get("id"):
                    answer_id = task_data["answer"]["id"]
                
                ai_res = await resolve_task_answers(task_data, tid)
                if not ai_res.get("success") or not ai_res.get("answers"):
                    raise Exception("IA não retornou respostas válidas.")
                
                answers = ai_res["answers"]
                logger.info(f"[{tid}] Respostas resolvidas com sucesso! Aguardando delay de {delay_minutes} min...")
                
                # Aguardar delay
                delay_sec = delay_minutes * 60.0
                start_delay = time.time()
                task_state["status"] = "waiting_delay"
                task_state["total_delay"] = delay_sec
                
                while True:
                    elapsed = time.time() - start_delay
                    remaining = max(0, delay_sec - elapsed)
                    task_state["remaining_seconds"] = round(remaining)
                    task_state["message"] = f"Aguardando delay humanizado ({round(remaining)}s restantes)..."
                    if remaining <= 0:
                        break
                    write_status(state)
                    await asyncio.sleep(min(10.0, remaining))
                
                # Submeter respostas
                logger.info(f"[{tid}] Enviando respostas...")
                task_state["status"] = "submitting"
                task_state["message"] = "Submetendo respostas..."
                write_status(state)
                
                for entry in answers.values():
                    if isinstance(entry, dict) and entry.get("question_type") == "fill-letters":
                        ans_v = entry.get("answer")
                        if isinstance(ans_v, list):
                            entry["answer"] = "".join(str(x) for x in ans_v)
                
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
                    "x-api-key": auth_token
                }
                
                submit_payload = {
                    "status": "submitted",
                    "answers": answers,
                    "accessed_on": "room",
                    "executed_on": room_name,
                    "duration": delay_sec
                }
                
                if answer_id:
                    url_sub = f"{IPTV_BASE_URL}/tms/task/{tid}/answer/{answer_id}"
                    resp_sub = await client.put(url_sub, json=submit_payload, headers=headers_submit)
                else:
                    url_sub = f"{IPTV_BASE_URL}/tms/task/{tid}/answer"
                    resp_sub = await client.post(url_sub, json=submit_payload, headers=headers_submit)
                
                if resp_sub.status_code != 200:
                    raise Exception(f"Falha ao submeter: HTTP {resp_sub.status_code} - {resp_sub.text[:200]}")
                
                res_data = resp_sub.json() if resp_sub.text else {}
                score = res_data.get("score")
                logger.info(f"[{tid}] Tarefa concluída com sucesso! Pontuação: {score}")
                
                task_state["status"] = "completed"
                task_state["score"] = score
                task_state["message"] = f"Concluído com sucesso! Pontuação: {score}"
                state["completed"] += 1
                write_status(state)
                
            except Exception as e:
                logger.error(f"[{tid}] Erro na tarefa: {e}")
                task_state["status"] = "failed"
                task_state["message"] = f"Erro: {str(e)[:200]}"
                write_status(state)
        
        # Executar todas em paralelo
        await asyncio.gather(*(process_task(t) for t in pending_tasks))
        
        state["status"] = "finished"
        state["finish_time"] = time.time()
        write_status(state)
        logger.info("Todas as tarefas do lote foram finalizadas!")

if __name__ == "__main__":
    asyncio.run(run_batch(
        ra=os.environ.get("SALADOPASSADO_RA"),
        password=os.environ.get("SALADOPASSADO_PASSWORD"),
    ))
