import asyncio
import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SED_LOGIN_URL, SED_VALIDA_URL, SED_SUBSCRIPTION_KEY, IPTV_TOKEN_URL, IPTV_BASE_URL
from client import HttpCloakClient, _get_browser_context
from captcha_solver import tms_apply_with_captcha
from ai_solver import resolve_task_answers
from database import init_db

async def test_resolve_first_task():
    init_db()
    ra_part = os.environ.get("TEST_RA", "")
    digito = os.environ.get("TEST_DIGITO", "")
    uf = os.environ.get("TEST_UF", "SP")
    password = os.environ.get("TEST_PASSWORD", "")
    if not ra_part or not digito or not password:
        raise SystemExit(
            "Defina TEST_RA, TEST_DIGITO e TEST_PASSWORD no ambiente para rodar este smoke test. "
            "Nunca commite credenciais reais."
        )
    constructed_user = f"{ra_part}{digito}{uf}"
    
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
        data_sed = resp_sed.json()
        token_sed = data_sed.get("token")
        
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
        room_name = rooms[0].get("name", "") if rooms else ""
        
        task_id = 99752335
        url_apply = f"{IPTV_BASE_URL}/tms/task/{task_id}/apply?preview_mode=false&token_code=null&room_name={room_name}"
        
        print(f"Applying task {task_id} with captcha solver...")
        resp_apply = await tms_apply_with_captcha(client, url_apply, headers_tms, task_id)
        print("Apply status code:", resp_apply.status_code)
        task_data = resp_apply.json()
        print("Task Title:", task_data.get("title"))
        
        print("Resolving answers with AI...")
        res = await resolve_task_answers(task_data, task_id)
        print("AI Result:", json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(test_resolve_first_task())
