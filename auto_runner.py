import asyncio
import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SED_LOGIN_URL, SED_VALIDA_URL, SED_SUBSCRIPTION_KEY, IPTV_TOKEN_URL, IPTV_BASE_URL
from client import HttpCloakClient, _get_browser_context

async def list_pending_tasks(ra=None, password=None):
    if not ra or not password:
        raise SystemExit(
            "Informe RA e senha via argumentos ou env (SALADOPASSADO_RA / SALADOPASSADO_PASSWORD). "
            "Nunca commite credenciais reais."
        )
    ra_part = ra.split("-")[0].replace(" ", "").lstrip("0")
    rest = ra.split("-")[1].strip().split()
    digito = rest[0]
    uf = rest[1].upper() if len(rest) > 1 else "SP"
    constructed_user = f"{ra_part}{digito}{uf}"
    
    print(f"User: {constructed_user}")
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
            json={"user": constructed_user, "senha": password},
            headers=headers_login
        )
        if resp_sed.status_code != 200:
            print(f"SED login failed: {resp_sed.status_code} - {resp_sed.text}")
            return None
        
        data_sed = resp_sed.json()
        token_sed = data_sed.get("token")
        user_info = data_sed.get("DadosUsuario", {})
        student_name = user_info.get("NAME") or user_info.get("Nome") or "Estudante"
        print(f"Student: {student_name}")
        
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
            print(f"IPTV login failed: {resp_iptv.status_code} - {resp_iptv.text}")
            return None
            
        iptv_data = resp_iptv.json()
        auth_token = iptv_data.get("auth_token")
        nick = iptv_data.get("nick")
        
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
        
        url_essays = f"{IPTV_BASE_URL}/tms/task/todo?expired_only=false&limit=100&offset=0&filter_expired=true&is_exam=false&with_answer=true&is_essay=true&{targets_query}&with_apply_moment=true"
        resp_essays = await client.get(url_essays, headers=headers_tms)
        essays_raw = resp_essays.json() if resp_essays.status_code == 200 else []
        
        pending_tasks = [t for t in tasks_raw if t.get("answer_status") not in ("finished", "submitted")]
        pending_essays = [t for t in essays_raw if t.get("answer_status") not in ("finished", "submitted")]
        
        print(f"Total Pending Tasks: {len(pending_tasks)}")
        for t in pending_tasks:
            print(f" - [ID: {t.get('id')}] {t.get('title')}")
            
        print(f"Total Pending Essays: {len(pending_essays)}")
        for e in pending_essays:
            print(f" - [ID: {e.get('id')}] {e.get('title')}")
            
        return {
            "name": student_name,
            "tasks": pending_tasks,
            "essays": pending_essays
        }

if __name__ == "__main__":
    asyncio.run(list_pending_tasks(
        ra=os.environ.get("SALADOPASSADO_RA"),
        password=os.environ.get("SALADOPASSADO_PASSWORD"),
    ))
