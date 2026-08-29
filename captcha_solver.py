import asyncio
import base64
import logging
import os
import tempfile
import uuid
from config import IPTV_BASE_URL, CAPTCHA_SOLVER_PYTHON, CAPTCHA_PREDICT_SCRIPT

logger = logging.getLogger("saladopassado.captcha")

_ORIGIN = "https://saladofuturo.educacao.sp.gov.br"
_REFERER = "https://saladofuturo.educacao.sp.gov.br/"

_FINGERPRINT_HEADERS = (
    "user-agent", "User-Agent",
    "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "x-api-key", "x-api-platform", "x-api-realm",
    "accept-language", "Accept-Language",
)

def new_session_key() -> str:
    return uuid.uuid4().hex

async def predict_captcha_answer(image_bytes: bytes, python: str = None) -> str:
    """Run the CNN predictor on a decoded captcha PNG and return the word."""
    py_exec = python or CAPTCHA_SOLVER_PYTHON
    if not os.path.isfile(CAPTCHA_PREDICT_SCRIPT):
        raise RuntimeError(f"Predictor não encontrado em: {CAPTCHA_PREDICT_SCRIPT}")
    
    with tempfile.TemporaryDirectory(prefix="captcha_") as tmp:
        img_path = os.path.join(tmp, "captcha.png")
        with open(img_path, "wb") as f:
            f.write(image_bytes)
            
        proc = await asyncio.create_subprocess_exec(
            py_exec, CAPTCHA_PREDICT_SCRIPT, img_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = (stderr or b"").decode(errors="replace").strip()
            raise RuntimeError(f"predict_captcha.py falhou (rc={proc.returncode}): {err[:400]}")
        
        answer = (stdout or b"").decode(errors="replace").strip().lower()
        if not answer:
            raise RuntimeError("predict_captcha.py não retornou resposta")
        return answer

def _captcha_headers(session_key: str, headers_base: dict = None) -> dict:
    hdrs = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": _ORIGIN,
        "referer": _REFERER,
        "x-session-key": session_key,
    }
    if headers_base:
        for k in _FINGERPRINT_HEADERS:
            if k in headers_base and headers_base[k]:
                hdrs[k] = headers_base[k]
    return hdrs

async def solve_edusp_captcha(
    client,
    headers_base: dict = None,
    session_key: str = None,
    max_attempts: int = 3,
    python: str = None,
) -> str:
    """Full challenge -> CNN solve -> verify loop. Returns x-captcha-token."""
    session_key = session_key or new_session_key()
    hdrs = _captcha_headers(session_key, headers_base)

    for _ in range(max_attempts):
        try:
            r = await client.post(
                f"{IPTV_BASE_URL}/captcha/challenge",
                json={"realm": "edusp"},
                headers=hdrs,
            )
        except Exception as e:
            raise RuntimeError(f"captcha/challenge erro de rede: {e}") from e

        if r.status_code != 200:
            raise RuntimeError(f"captcha/challenge HTTP {r.status_code}: {r.text[:300]}")

        ch = r.json()
        challenge_id = ch.get("challengeId")
        img_b64 = (ch.get("challenge") or {}).get("image")
        if not challenge_id or not img_b64:
            raise RuntimeError(f"captcha/challenge resposta inesperada: {str(ch)[:300]}")

        image_bytes = base64.b64decode(img_b64)
        answer = await predict_captcha_answer(image_bytes, python=python)

        try:
            v = await client.post(
                f"{IPTV_BASE_URL}/captcha/verify",
                json={
                    "type": "image",
                    "realm": "edusp",
                    "payload": {"challengeId": challenge_id, "answer": answer},
                },
                headers=hdrs,
            )
        except Exception as e:
            raise RuntimeError(f"captcha/verify erro de rede: {e}") from e

        if v.status_code == 200:
            vj = v.json() if hasattr(v, "json") else {}
            if vj.get("valid") and vj.get("token"):
                return vj["token"]

        session_key = new_session_key()
        hdrs = _captcha_headers(session_key, headers_base)

    raise RuntimeError(f"Falha ao resolver CAPTCHA após {max_attempts} tentativas.")

async def tms_apply_with_captcha(
    client,
    url_apply: str,
    headers_tms: dict,
    task_id: int,
    known_enable_captcha: bool = None,
    max_attempts: int = 3,
    python: str = None,
):
    """Wrapper that resolves CAPTCHA when necessary and executes apply."""
    headers_req = dict(headers_tms)
    
    if known_enable_captcha is True:
        token = await solve_edusp_captcha(
            client, headers_base=headers_tms, max_attempts=max_attempts, python=python
        )
        headers_req["x-captcha-token"] = token
        return await client.get(url_apply, headers=headers_req)

    if known_enable_captcha is False:
        return await client.get(url_apply, headers=headers_req)

    resp = await client.get(url_apply, headers=headers_req)
    if resp.status_code == 200:
        return resp

    body_low = (resp.text or "").lower()
    if resp.status_code in (400, 401, 403, 412, 422, 429) or "captcha" in body_low or "verificação" in body_low:
        token = await solve_edusp_captcha(
            client, headers_base=headers_tms, max_attempts=max_attempts, python=python
        )
        headers_req["x-captcha-token"] = token
        return await client.get(url_apply, headers=headers_req)

    return resp
