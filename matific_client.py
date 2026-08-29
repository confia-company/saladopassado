import asyncio
import datetime
import json
import logging
import random
import re
import time
import urllib.parse
import uuid
from typing import Optional

from client import HttpCloakClient, RoutingAsyncClient, _get_browser_context
from config import SED_LOGIN_URL, SED_VALIDA_URL, SED_SUBSCRIPTION_KEY

logger = logging.getLogger("saladopassado.matific")

# Global cache for problem IDs so the same episode+index always gets the same ID
_PROBLEM_ID_CACHE: dict[tuple[str, int], str] = {}

def _extract_cookie_val(client, cookie_name: str) -> Optional[str]:
    """Extract a cookie value from HttpCloakClient (checking both proxied and direct sessions)."""
    if not client:
        return None
    if hasattr(client, "get_cookie"):
        try:
            val = client.get_cookie(cookie_name)
            if val:
                if isinstance(val, str):
                    return val
                if hasattr(val, "value"):
                    return val.value
        except Exception:
            pass
    for s_attr in ("proxy_session", "session"):
        session = getattr(client, s_attr, None)
        if session:
            if hasattr(session, "get_cookie"):
                try:
                    c = session.get_cookie(cookie_name)
                    if c:
                        return c.value if hasattr(c, "value") else str(c)
                except Exception:
                    pass
            if hasattr(session, "get_cookies"):
                try:
                    for c in session.get_cookies():
                        if getattr(c, "name", None) == cookie_name:
                            return c.value
                except Exception:
                    pass
            if hasattr(session, "cookies"):
                try:
                    val = session.cookies.get(cookie_name)
                    if val:
                        return val
                except Exception:
                    pass
    return None

_MATIFIC_PART_NAME_MAP = {
    "Aircraft_Body": "Body",
    "Aircraft_Wings": "Wings",
    "Aircraft_Wheels": "Wheels",
    "Aircraft_Balloon": "Balloon",
    "Aircraft_Seat": "Seat",
    "Outfit_Torso": "Torso",
    "Outfit_Legs": "Legs",
    "Outfit_Head": "Head",
    "Outfit_Face": "Face",
    "Outfit_Skin": "Color",
    "Outfit_Hands": "Hands",
    "Outfit_Feets": "Feets",
}

EVENTS_WITH_DEVICEINFO = {
    "AppInitComplete", "ContainerReportedUserFinished", "EpisodeClicked",
    "EpisodeDetailsSentToContainer", "EpisodeInvoked", "EpisodeLoadingShown",
    "EpisodeOpen", "EpisodePostScreenUserAction", "EpisodesEnrichmentFetchAttempt",
    "EpisodesEnrichmentSuccess", "GameStateFetchAttempt", "GameStatePopulated",
    "GameStateReceived", "InitDataAttempt", "InitDataParsingSuccess",
    "InitDataPopulationSuccess", "LoadingAvatarSkins", "MandatoryAssetsFetchAttempt",
    "MandatoryAssetsFetchCompleted", "ScreenViewLoaded", "screen_view",
    "EpisodeFinished", "EpisodeRunning", "EpisodeReady", "EpisodeLoadingStarted",
    "EpisodeInteraction",
}

GPU_STRINGS = [
    "ANGLE (Intel, Mesa Intel(R) UHD Graphics (TGL GT1), OpenGL 4.6)",
    "ANGLE (Intel, Intel(R) UHD Graphics 620, OpenGL 4.5)",
    "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)",
]

MATIFIC_TRANSLATIONS = {
    "WorksheetWholePowersFractions": "Potências Inteiras de Frações",
    "WorksheetWholePowersMixedFluency": "Fluência Mista em Potências Inteiras",
    "WorksheetRationalPowersRadicalsAdvanced": "Potências Racionais e Radicais (Avançado)",
    "WorksheetRadicalsSquareRootsEstimation": "Estimativa de Radicais e Raízes Quadradas",
    "PolygonStackTriangles": "Empilhamento de Polígonos: Triângulos",
    "WorksheetTriangleSimilarityRecognizingSimilarTriangles": "Semelhança de Triângulos: Reconhecendo Triângulos Semelhantes",
    "WorksheetThalesTrapezoidMultipleMain": "Teorema de Tales: Trapézios Múltiplos",
    "WorksheetPolygonsTriangleAngleSum": "Soma dos Ângulos Internos de um Triângulo",
    "WorksheetPythagorasGeometricProofMain": "Teorema de Pitágoras: Demonstração Geométrica",
    "WorksheetRepeatingDecimalConversionConvert": "Conversão de Dízimas Periódicas",
    "EstimatingOnTheNumberLineSquareRoots": "Estimando Raízes Quadradas na Reta Numérica",
    "WorksheetFractionalExponentsWholeNumbersMain": "Expoentes Fracionários e Números Inteiros",
    "WorksheetPowersAndBasesDifferentBasesSimplify": "Simplificação de Potências e Bases Diferentes",
    "WorksheetPowerLawsNegativePowersAndBases": "Leis das Potências: Potências e Bases Negativas",
    "WorksheetCompletingTheSquareMain": "Completando o Quadrado",
    "WorksheetQuadraticsCompleteTheSquareAbstractMain": "Equações Quadráticas: Completando Quadrados (Abstrato)",
}

WORD_TRANSLATIONS = {
    "addition": "Adição", "subtraction": "Subtração", "multiplication": "Multiplicação", "division": "Divisão",
    "decimals": "Decimais", "decimal": "Decimal", "fractions": "Frações", "fraction": "Fração",
    "whole": "Inteiro", "numbers": "Números", "number": "Número", "estimation": "Estimativa", "estimating": "Estimativa",
    "wordproblems": "Problemas Verbais", "powers": "Potências", "power": "Potência", "bases": "Bases", "base": "Base",
    "radicals": "Radicais", "radical": "Radical", "roots": "Raízes", "root": "Raiz", "similarity": "Semelhança",
    "similar": "Semelhante", "polygons": "Polígonos", "polygon": "Polígono", "triangles": "Triângulos", "triangle": "Triângulo",
    "square": "Quadrado", "geometric": "Geométrico", "proof": "Demonstração", "repeating": "Dízima",
    "conversion": "Conversão", "convert": "Converter", "laws": "Leis", "negative": "Negativas",
    "different": "Diferentes", "simplify": "Simplificar", "advanced": "Avançado", "basic": "Básico",
    "fluency": "Fluência", "mixed": "Misto", "with": "com", "and": "e", "of": "de", "by": "por", "on": "na",
    "line": "Reta", "thales": "Tales", "trapezoid": "Trapézio", "multiple": "Múltiplos", "main": "Principal",
    "stack": "Pilha", "completing": "Completando", "quadratics": "Quadráticas", "abstract": "Abstrato",
}

def translate_matific_slug(slug: str) -> str:
    if not slug:
        return ""
    if slug in MATIFIC_TRANSLATIONS:
        return MATIFIC_TRANSLATIONS[slug]
    cleaned = slug
    if cleaned.startswith("Worksheet"):
        cleaned = cleaned[9:]
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", cleaned)
    translated = []
    for w in words:
        wl = w.lower()
        if wl in WORD_TRANSLATIONS:
            translated.append(WORD_TRANSLATIONS[wl])
        else:
            translated.append(w)
    res = " ".join(translated)
    res = res.replace(" Avançado", " (Avançado)").replace(" Básico", " (Básico)")
    return res

def _aggregate_played_episodes(game_state: dict) -> dict:
    """Collapse many per-instance game_state rows into one status per episode."""
    played = {}
    for ent in game_state.get("game_entity", []):
        if ent.get("object_type") != "Matific.Mad.EpisodeStorableData":
            continue
        ent_id = ent.get("entity_id")
        if not ent_id:
            continue
        was_passed = bool(ent.get("data", {}).get("wasPassed", False))
        highest_score = ent.get("highest_score")
        if not was_passed and highest_score is None:
            continue
        pe = played.setdefault(ent_id, {"was_passed": False, "highest_score": None})
        pe["was_passed"] = pe["was_passed"] or was_passed
        if highest_score is not None:
            pe["highest_score"] = max(pe["highest_score"] or 0, highest_score)
    return played


class MatificClient:
    def __init__(self, ra: str, digito: str, uf: str, password: str, fp: dict = None):
        self.ra = ra.strip().lstrip('0') or ra.strip()
        self.digito = digito.strip()
        self.uf = uf.strip().upper()
        self.password = password
        self.fp = fp or _get_browser_context()
        self.client: Optional[HttpCloakClient] = None
        self.user_data_token: Optional[str] = None
        self.csrftoken: Optional[str] = None
        self.sessionid: Optional[str] = None
        self.slatemath_user_id: Optional[str] = None
        self.firebase_token: Optional[str] = None
        self.firebase_config: Optional[dict] = None
        self.firebase_id_token: Optional[str] = None
        self.firebase_refresh_token: Optional[str] = None
        self.firebase_student_id: Optional[str] = None
        self.firebase_api_key: Optional[str] = None
        self.firebase_project_id: Optional[str] = None
        self.chrome_version = self.fp["user-agent"].split("Chrome/")[1].split(" ")[0]
        self._current_memory = random.choice([79, 95, 115, 165, 198])
        self.init_data: Optional[dict] = None
        self.app_version = "7.21.0"
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9",
            "User-Agent": self.fp["user-agent"],
            "sec-ch-ua": self.fp["sec-ch-ua"],
            "sec-ch-ua-mobile": self.fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": self.fp["sec-ch-ua-platform"],
        }

    async def __aenter__(self):
        self.client = HttpCloakClient(timeout=30.0)
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def authenticate(self) -> bool:
        """SSO Login Flow for Matific via SED BFF."""
        self.client.set_default_headers(self.headers)
        self.client.set_cookie("to_lite_version", "false", domain="www.matific.com")

        # 1. Login on SED BFF
        constructed_user = f"{self.ra.zfill(12)}{self.digito}{self.uf}"
        payload_login = {"user": constructed_user, "senha": self.password}
        headers_login = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": SED_SUBSCRIPTION_KEY,
            "X-Product-Name": "SalaDoFuturo",
            "Origin": "https://saladofuturo.educacao.sp.gov.br",
            "Referer": "https://saladofuturo.educacao.sp.gov.br/",
            "User-Agent": self.fp["user-agent"],
            "sec-ch-ua": self.fp["sec-ch-ua"],
            "sec-ch-ua-mobile": self.fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": self.fp["sec-ch-ua-platform"],
        }
        
        logger.info(f"[MATIFIC-AUTH] Logging in student {constructed_user} on SED...")
        resp_login = await self.client.post(
            SED_LOGIN_URL,
            json=payload_login,
            headers=headers_login
        )
        if resp_login.status_code != 200:
            logger.error(f"[MATIFIC-AUTH] SED login failed: HTTP {resp_login.status_code}")
            return False
            
        data_login = resp_login.json()
        token_sed = data_login.get("token")
        if not token_sed:
            logger.error("[MATIFIC-AUTH] SED login response missing token.")
            return False
            
        # 2. Validate token
        headers_valida = {
            "Ocp-Apim-Subscription-Key": SED_SUBSCRIPTION_KEY,
            "X-Product-Name": "SalaDoFuturo",
            "Authorization": f"Bearer {token_sed}",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "User-Agent": self.fp["user-agent"],
            "sec-ch-ua": self.fp["sec-ch-ua"],
            "sec-ch-ua-mobile": self.fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": self.fp["sec-ch-ua-platform"],
        }
        await self.client.post(SED_VALIDA_URL, headers=headers_valida)
        
        # 3. Get platform token (SSO JWT)
        url_token = "https://sedintegracoes.educacao.sp.gov.br/saladofuturobffapi/integracoes/Token?plataforma=Matific"
        headers_token = {
            "Ocp-Apim-Subscription-Key": SED_SUBSCRIPTION_KEY,
            "X-Product-Name": "SalaDoFuturo",
            "Authorization": f"Bearer {token_sed}",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "User-Agent": self.fp["user-agent"],
            "sec-ch-ua": self.fp["sec-ch-ua"],
            "sec-ch-ua-mobile": self.fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": self.fp["sec-ch-ua-platform"],
        }
        resp_tok = await self.client.get(url_token, headers=headers_token)
        if resp_tok.status_code != 200:
            logger.error(f"[MATIFIC-AUTH] Failed to get Matific integration token: HTTP {resp_tok.status_code}")
            return False
            
        matific_jwt = resp_tok.json().get("data")
        if not matific_jwt:
            logger.error("[MATIFIC-AUTH] Integration token response missing data field.")
            return False
            
        # 4. Exchange Matific JWT on sso.matific.com redirect endpoint
        sso_url = f"https://sso.matific.com/api/v2/integrations/login?vendor_id=25&vendor_token={matific_jwt}"
        logger.info("[MATIFIC-AUTH] Exchanging platform JWT for Matific session cookies...")
        resp_sso = await self.client.get(sso_url, headers=self.headers)
        if resp_sso.status_code != 200:
            logger.error(f"[MATIFIC-AUTH] SSO handoff failed: HTTP {resp_sso.status_code}")
            return False
            
        self.sessionid = _extract_cookie_val(self.client, "sessionid")
        self.user_data_token = _extract_cookie_val(self.client, "user_data_token")
        self.csrftoken = _extract_cookie_val(self.client, "csrftoken")
        self.slatemath_user_id = _extract_cookie_val(self.client, "slatemath_user_id")
        
        if not self.sessionid or not self.user_data_token:
            logger.error("[MATIFIC-AUTH] Failed to establish cookies in redirect chain.")
            return False

        # Extract active app version dynamically
        try:
            site_v2_url = "https://www.matific.com/bra/pt-br/student-site-v2"
            resp_site_v2 = await self.client.get(site_v2_url)
            match = re.search(r"/students/app/([^/]+)/", str(resp_site_v2.url))
            if match:
                self.app_version = match.group(1)
                logger.info(f"[MATIFIC-AUTH] Dynamically detected active Matific app version: {self.app_version}")
        except Exception as e:
            logger.warning(f"[MATIFIC-AUTH] Using fallback app version {self.app_version} ({e})")
            
        logger.info(f"[MATIFIC-AUTH] Matific authentication successful! token={self.user_data_token[:10]}...")
        return True

    async def get_init_data(self) -> dict:
        """Fetch general init data for campaigns, assignments, and user settings"""
        url = f"https://www.matific.com/api/student-site-v2/game-initialization-data/?exclude_firebase_token=true&app_version={self.app_version}&platform=WebGLPlayer"
        headers = {
            "X-CSRFToken": self.csrftoken or "",
            "Referer": f"https://www.matific.com/students/app/{self.app_version}/",
            **self.headers
        }
        resp = await self.client.get(url, headers=headers)
        if resp.status_code in (401, 403):
            logger.warning(f"[MATIFIC-API] Got {resp.status_code} in get_init_data, re-authenticating...")
            if await self.authenticate():
                headers["X-CSRFToken"] = self.csrftoken or ""
                resp = await self.client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"[MATIFIC-API] Failed to get initialization data: HTTP {resp.status_code}")
            return {}
        self.init_data = resp.json()
        return self.init_data

    async def get_episode_enrichment(self) -> dict:
        """Fetch episode enrichment JSON mapping EpisodeId -> {Slug, Title, Subtitle}."""
        if not self.init_data:
            await self.get_init_data()
        enrich_url = (self.init_data or {}).get("Urls", {}).get("EpisodeEnrichmentUrl")
        if not enrich_url:
            return {}
        headers = {
            "Accept": "*/*",
            "Referer": "https://www.matific.com/",
            **self.headers
        }
        resp = await self.client.get(enrich_url, headers=headers)
        if resp.status_code != 200:
            return {}
        return resp.json()

    async def generate_firebase_token(self) -> dict:
        url = "https://www.matific.com/api/student-site-v2/generate-firebase-token/"
        headers = {
            "X-CSRFToken": self.csrftoken or "",
            "Referer": f"https://www.matific.com/students/app/{self.app_version}/",
            **self.headers
        }
        data = {
            "app_version": self.app_version,
            "platform": "WebGLPlayer"
        }
        resp = await self.client.post(url, data=data, headers=headers)
        if resp.status_code != 200:
            return {}
        res_json = resp.json()
        self.firebase_token = res_json.get("FirebaseToken")
        self.firebase_config = res_json.get("FirebaseConfig")
        return res_json

    async def get_firebase_config(self) -> dict:
        url = "https://www.matific.com/api/v2/accounts/firebase-config/"
        headers = {
            "X-CSRFToken": self.csrftoken or "",
            "Referer": f"https://www.matific.com/students/app/{self.app_version}/",
            **self.headers,
        }
        try:
            resp = await self.client.get(url, headers=headers)
            if resp.status_code != 200:
                return {}
            data = resp.json()
            cfg = data.get("firebase_config") or {}
            self.firebase_api_key = cfg.get("apiKey")
            self.firebase_project_id = cfg.get("projectId")
            if data.get("user_token") and not self.firebase_token:
                self.firebase_token = data["user_token"]
            return data
        except Exception:
            return {}

    async def exchange_firebase_token(self) -> bool:
        if not self.firebase_token or not self.firebase_api_key or not self.firebase_project_id:
            return False
        try:
            identity_url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyCustomToken?key={self.firebase_api_key}"
            async with RoutingAsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    identity_url,
                    json={"token": self.firebase_token, "returnSecureToken": True},
                )
            if resp.status_code != 200:
                return False
            data = resp.json()
            self.firebase_id_token = data.get("idToken")
            self.firebase_refresh_token = data.get("refreshToken")
            self.firebase_student_id = data.get("localId") or self.slatemath_user_id
            return True
        except Exception:
            return False

    def _firestore_timestamp(self, epoch_ms: int) -> str:
        dt = datetime.datetime.fromtimestamp(epoch_ms / 1000, datetime.timezone.utc)
        ms_part = epoch_ms % 1000
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms_part:03d}000000Z"

    def _firestore_value(self, v):
        if isinstance(v, dict):
            if "$ts" in v:
                return {"timestampValue": v["$ts"]}
            return {"mapValue": {"fields": {fk: self._firestore_value(fv) for fk, fv in v.items()}}}
        elif isinstance(v, bool):
            return {"booleanValue": v}
        elif isinstance(v, str):
            return {"stringValue": v}
        elif isinstance(v, int):
            return {"integerValue": str(v)}
        elif isinstance(v, float):
            return {"doubleValue": v}
        elif v is None:
            return {"nullValue": None}
        elif isinstance(v, list):
            return {"arrayValue": {"values": [self._firestore_value(item) for item in v]}}
        return {"stringValue": str(v)}

    def _firestore_body(self, plain: dict) -> dict:
        fields = {k: self._firestore_value(v) for k, v in plain.items()}
        return {"fields": fields}

    async def _write_firestore_doc(self, collection_path: str, doc_id: str, plain: dict) -> bool:
        if not self.firebase_id_token or not self.firebase_project_id:
            return False
        try:
            base = f"https://firestore.googleapis.com/v1/projects/{self.firebase_project_id}/databases/(default)/documents"
            url = f"{base}/{collection_path}/{doc_id}"
            body = self._firestore_body(plain)
            async with RoutingAsyncClient(timeout=10.0) as http:
                resp = await http.patch(url, json=body, headers={"Authorization": f"Bearer {self.firebase_id_token}"})
            return resp.status_code in (200, 201)
        except Exception:
            return False

    async def _send_live_class_login(self, class_id: str, session_start_ms: int) -> bool:
        client_time = int(time.time() * 1000)
        expires_ms = client_time + 7_200_000
        doc_id = str(uuid.uuid4())
        plain = {
            "type": "Login",
            "student_id": self.firebase_student_id or "",
            "platform": "WEBGL",
            "client_time": client_time,
            "session_identifier": session_start_ms,
            "expires_at": {"$ts": self._firestore_timestamp(expires_ms)},
        }
        return await self._write_firestore_doc(f"live-classes/{class_id}/fact-events", doc_id, plain)

    async def _send_live_class_keep_alive(self, class_id: str) -> bool:
        client_time = int(time.time() * 1000)
        expires_ms = client_time + 7_200_000
        plain = {"expires_at": {"$ts": self._firestore_timestamp(expires_ms)}}
        return await self._write_firestore_doc(f"live-classes/{class_id}/fact-events", "keep-alive", plain)

    async def _live_class_login_loop(self, class_id: str, session_start_ms: int, stop_event: asyncio.Event):
        last_keep_alive = 0
        while not stop_event.is_set():
            now = time.time()
            try:
                await self._send_live_class_login(class_id, session_start_ms)
                if now - last_keep_alive >= 15.0:
                    await self._send_live_class_keep_alive(class_id)
                    last_keep_alive = now
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=9.0)
            except asyncio.TimeoutError:
                pass

    async def _send_live_class_episode_results(
        self,
        class_id: str,
        episode: dict,
        origin_id: str,
        event_type: str,
        answers_list: list,
        problem_count: int,
        start_time_ms: int,
    ) -> bool:
        slug = episode.get("slug", "")
        student_id = self.firebase_student_id or self.slatemath_user_id or ""
        client_time = int(time.time() * 1000)
        expire_ms = client_time + 7_200_000
        doc_id = f"{student_id}-{slug}-{origin_id}" if origin_id else f"{student_id}-{slug}"
        plain = {
            "type": "episode-results",
            "event_type": event_type,
            "student_id": student_id,
            "origin_id": origin_id,
            "episode_slug": slug,
            "episode_name": episode.get("dev_name") or episode.get("name") or slug,
            "episode_type": episode.get("type") or "Worksheet",
            "activity_context": str(episode.get("context_id") or episode.get("activity_context") or "1"),
            "problem_count": problem_count,
            "start_time": start_time_ms,
            "client_time": client_time,
            "expires_at": {"$ts": self._firestore_timestamp(expire_ms)},
            "answers": answers_list,
        }
        return await self._write_firestore_doc(f"live-classes/{class_id}/fact-events", doc_id, plain)

    async def fetch_game_state(self, campaign_ids: list) -> dict:
        campaign_ids_str = urllib.parse.quote(json.dumps(campaign_ids))
        url = f"https://prod-madgames2fetch.matific.com/?platform=WebGLPlayer&app_version={self.app_version}&data_version=0&type=fetch_account_data&object_types=%5B%5D&campaigns_ids={campaign_ids_str}"
        headers = {
            "Accept": "*/*",
            "Origin": "https://www.matific.com",
            "Referer": "https://www.matific.com/",
            "x-userdata-token": self.user_data_token,
            "X-CSRFToken": self.csrftoken or "",
            **self.headers
        }
        resp = await self.client.get(url, headers=headers)
        if resp.status_code != 200:
            return {}
        return resp.json()

    async def store_game_state(self, rows: list) -> bool:
        url = "https://prod-madgames2store.matific.com/"
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://www.matific.com",
            "Referer": "https://www.matific.com/",
            "x-userdata-token": self.user_data_token,
            "X-CSRFToken": self.csrftoken or "",
            **self.headers
        }
        payload = {
            "platform": "WebGLPlayer",
            "app_version": self.app_version,
            "token": self.user_data_token,
            "type": "upsert",
            "rows": rows
        }
        resp = await self.client.post(url, headers=headers, json=payload)
        return resp.status_code == 200

    async def fetch_inventory_and_customization(self, campaign_id: str) -> dict:
        game_state = await self.fetch_game_state(campaign_ids=[campaign_id])
        user_state = game_state.get("user_state", [])
        
        currency_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.CurrencyData"), None)
        ranking_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.RankingData"), None)
        weekly_goal_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.UserGoalProgressData" and r.get("item_id") == "weekly_goal"), None)
        inventory_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.AvailableInventoryItemsData"), None)
        customization_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.CustomizedItemsData"), None)
        
        coins = currency_row["data"].get("currentCoins", 0) if currency_row else 0
        xp = ranking_row["data"].get("currentXp", 0) if ranking_row else 0
        rank = ranking_row["data"].get("currentRank", 1) if ranking_row else 1
        weekly_goal = weekly_goal_row["data"].get("progress", 0) if weekly_goal_row else 0
        weekly_goal_target = 1800
        
        inventory = inventory_row["data"].get("availableItems", []) if inventory_row else []
        customization = customization_row["data"].get("itemIdByItemPart", {}) if customization_row else {}
        
        return {
            "coins": coins,
            "xp": xp,
            "rank": rank,
            "weekly_goal": weekly_goal,
            "weekly_goal_target": weekly_goal_target,
            "inventory": inventory,
            "customization": customization,
            "currency_row": currency_row,
            "inventory_row": inventory_row,
            "customization_row": customization_row
        }

    async def purchase_item(self, campaign_id: str, item_id: str, cost: int) -> bool:
        state = await self.fetch_inventory_and_customization(campaign_id)
        currency_row = state["currency_row"]
        inventory_row = state["inventory_row"]
        if not currency_row or not inventory_row:
            return False
        current_coins = state["coins"]
        if current_coins < cost:
            return False
        currency_data = currency_row["data"].copy()
        currency_data["currentCoins"] = current_coins - cost
        inventory_data = inventory_row["data"].copy()
        owned_items = list(inventory_data.get("availableItems", []))
        if item_id not in owned_items:
            owned_items.append(item_id)
        inventory_data["availableItems"] = owned_items
        rows = [
            {
                "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                "table_name": "user_state",
                "row_id": currency_row["row_id"],
                "data_version_number": 0,
                "object_type": "Matific.Mad.CurrencyData",
                "data": currency_data,
                "deprecation_rule": None,
                "item_id": currency_row.get("item_id")
            },
            {
                "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                "table_name": "user_state",
                "row_id": inventory_row["row_id"],
                "data_version_number": 0,
                "object_type": "Matific.Mad.AvailableInventoryItemsData",
                "data": inventory_data,
                "deprecation_rule": None,
                "item_id": inventory_row.get("item_id")
            }
        ]
        return await self.store_game_state(rows)

    async def equip_item(self, campaign_id: str, part_name: str, item_id: str) -> bool:
        state = await self.fetch_inventory_and_customization(campaign_id)
        customization_row = state["customization_row"]
        inventory = state["inventory"]
        if not customization_row:
            return False
        is_default = "default" in item_id.lower() or "none" in item_id.lower() or item_id == ""
        if item_id not in inventory and not is_default:
            return False
        backend_part = _MATIFIC_PART_NAME_MAP.get(part_name, part_name)
        customization_data = customization_row["data"].copy()
        items = customization_data.get("itemIdByItemPart", {}).copy()
        items[backend_part] = item_id
        customization_data["itemIdByItemPart"] = items
        row = {
            "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
            "table_name": "user_state",
            "row_id": customization_row["row_id"],
            "data_version_number": 0,
            "object_type": "Matific.Mad.CustomizedItemsData",
            "data": customization_data,
            "deprecation_rule": None,
            "item_id": customization_row.get("item_id")
        }
        return await self.store_game_state([row])

    async def repair_customization(self, campaign_id: str) -> dict:
        state = await self.fetch_inventory_and_customization(campaign_id)
        customization_row = state["customization_row"]
        if not customization_row:
            return {"success": False, "repaired": []}
        customization_data = customization_row["data"].copy()
        items = customization_data.get("itemIdByItemPart", {}).copy()
        repaired = []
        corrupted = {k: v for k, v in items.items() if k in _MATIFIC_PART_NAME_MAP}
        if not corrupted:
            return {"success": True, "repaired": []}
        for bad_key, val in corrupted.items():
            good_key = _MATIFIC_PART_NAME_MAP[bad_key]
            items[good_key] = val
            del items[bad_key]
            repaired.append(f"{bad_key} -> {good_key}")
        customization_data["itemIdByItemPart"] = items
        row = {
            "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
            "table_name": "user_state",
            "row_id": customization_row["row_id"],
            "data_version_number": 0,
            "object_type": "Matific.Mad.CustomizedItemsData",
            "data": customization_data,
            "deprecation_rule": None,
            "item_id": customization_row.get("item_id")
        }
        ok = await self.store_game_state([row])
        return {"success": ok, "repaired": repaired}

    async def set_stats(self, campaign_id: str, coins: int = None, xp: int = None, rank: int = None) -> bool:
        state = await self.fetch_inventory_and_customization(campaign_id)
        rows = []
        if coins is not None and state.get("currency_row"):
            c_row = state["currency_row"]
            c_data = c_row["data"].copy()
            c_data["currentCoins"] = max(0, min(200000, coins))
            rows.append({
                "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                "table_name": "user_state",
                "row_id": c_row["row_id"],
                "data_version_number": 0,
                "object_type": "Matific.Mad.CurrencyData",
                "data": c_data,
                "deprecation_rule": None,
                "item_id": c_row.get("item_id")
            })
        if (xp is not None or rank is not None) and state.get("ranking_row"):
            r_row = state["ranking_row"]
            r_data = r_row["data"].copy()
            if xp is not None:
                r_data["currentXp"] = max(0, min(2000, xp))
            if rank is not None:
                r_data["currentRank"] = max(1, min(150, rank))
            rows.append({
                "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                "table_name": "user_state",
                "row_id": r_row["row_id"],
                "data_version_number": 0,
                "object_type": "Matific.Mad.RankingData",
                "data": r_data,
                "deprecation_rule": None,
                "item_id": r_row.get("item_id")
            })
        if not rows:
            return True
        return await self.store_game_state(rows)

    async def send_tracking_events_batch(self, events: list[dict]) -> bool:
        """Send a batch of telemetry tracking events to trackingevents.matific.com"""
        url = "https://trackingevents.matific.com/tracking_events"
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.user_data_token}",
            "Origin": "https://www.matific.com",
            "Referer": "https://www.matific.com/",
            **self.headers
        }
        payloads = []
        for ev in events:
            event_name = ev["event_name"]
            event_enum = ev["event_enum"]
            flow_run_id = ev.get("flow_run_id")
            app_run_id = ev.get("app_run_id")
            data = ev.get("data") or {}

            self._current_memory = min(256, max(64, self._current_memory + random.choice([-8, 0, 8])))

            payload = {
                "app_run_id": app_run_id,
                "environment": "com",
                "event_enum": event_enum,
                "flow_run_id": flow_run_id,
                "app_version": self.app_version,
                "platform": "WebGLPlayer",
                "subject": 0 if event_name not in ("GamePageLoad", "UnityInitStart", "UnityWasmLoaded", "UnityLoadCompleted", "UnityDataLoaded", "UnityLoadProgress") else -1,
                "client_time": time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}",
                "token": self.user_data_token,
                "data": {
                    "event_name": event_name,
                    "browser": f"Chrome/{self.chrome_version}",
                    **data
                }
            }

            if event_name in EVENTS_WITH_DEVICEINFO:
                payload["data"]["deviceinfo"] = {
                    "deviceModel": f"Chrome {self.chrome_version}",
                    "deviceUniqueIdentifier": "n/a",
                    "processorType": "n/a",
                    "systemMemorySize": str(self._current_memory),
                    "graphicsDeviceName": random.choice(GPU_STRINGS),
                    "graphicsMemorySize": "512",
                    "batteryLevel": "-1",
                    "operatingSystem": "Unknown OS Unknown OS Version"
                }
            payloads.append(payload)

        try:
            resp = await self.client.post(url, json=payloads, headers=headers)
            if resp.status_code in (401, 403):
                if await self.authenticate():
                    headers["Authorization"] = f"Bearer {self.user_data_token}"
                    for p in payloads:
                        p["token"] = self.user_data_token
                    resp = await self.client.post(url, json=payloads, headers=headers)
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"[MATIFIC-TRACKING] Tracking event warning (non-fatal): {e}")
            return True

    async def send_tracking_event(self, event_name: str, event_enum: int, flow_run_id: str, app_run_id: str, data: dict = None) -> bool:
        return await self.send_tracking_events_batch([{
            "event_name": event_name,
            "event_enum": event_enum,
            "flow_run_id": flow_run_id,
            "app_run_id": app_run_id,
            "data": data or {}
        }])

    async def _simulate_asset_loading(self):
        assets = [
            f"https://site1.matific.com/students/app/{self.app_version}/Build/ProductionWebGL.loader.js",
            f"https://site1.matific.com/students/app/{self.app_version}/Build/ProductionWebGL.framework.js.br",
            f"https://site1.matific.com/students/app/{self.app_version}/StreamingAssets/aa/WebGL/bundle_all.bundle",
            f"https://site1.matific.com/students/app/{self.app_version}/StreamingAssets/aa/catalog.json"
        ]
        tasks = [self.client.get(a, headers={"Accept": "*/*", "Referer": f"https://www.matific.com/students/app/{self.app_version}/", **self.headers}) for a in assets]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_ping(self):
        noise = random.random()
        url = f"https://ping.matific.com/ping.png?noise={noise:.16f}"
        headers = {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.matific.com/",
            **self.headers
        }
        try:
            await self.client.get(url, headers=headers)
        except Exception as e:
            logger.warning(f"[MATIFIC-PING] Ping warning (non-fatal): {e}")

    async def send_scoring_fact(self, fact: dict) -> bool:
        """Send scoring facts (StartEpisode, SubmitSolution, FinishEpisode)"""
        url = "https://prod-scoringservice.matific.com/addFacts"
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://www.matific.com",
            "Referer": "https://www.matific.com/",
            **self.headers
        }
        payload = {
            "user_data_token": self.user_data_token,
            "facts": [fact]
        }
        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            if resp.status_code in (401, 403):
                if await self.authenticate():
                    payload["user_data_token"] = self.user_data_token
                    resp = await self.client.post(url, json=payload, headers=headers)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[MATIFIC-SCORING] Scoring fact error: {e}")
            return False


    async def complete_episode(self, episode: dict, target_accuracy: str = "realistic", on_progress = None, timings: dict = None) -> bool:
        """Simulate playing an episode end-to-end with full telemetry, anti-detection delays and store persistence."""
        timings = timings or {}
        loading_multiplier = float(timings.get("loading_multiplier", 1.0))

        async def sleep_loading(min_s, max_s):
            await asyncio.sleep(random.uniform(min_s * loading_multiplier, max_s * loading_multiplier))

        def update_status(message, percent):
            if on_progress:
                on_progress(message, percent)

        app_run_id = str(uuid.uuid4())
        flow_run_id = str(uuid.uuid4())
        init_flow_run_id = str(uuid.uuid4())
        origin_id = "".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=10))
        episode_run_discriminator = time.strftime("%Y%m%d_%H") + "".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=16))

        slug = episode["slug"]
        assignment_id = episode.get("assignment_id")
        campaign_id = episode.get("campaign_id")
        context_id = str(episode.get("context_id", 13))
        episode_id = episode.get("episode_id")
        problem_count = episode.get("problem_count", 6) or 6

        dev_name = slug.replace("Advanced", "").replace("Basic", "")
        episode_instance_id = str(uuid.uuid4())

        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', dev_name)
        folder = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        if slug.endswith("Advanced"):
            param = "Parameters/Advanced"
        elif slug.endswith("Basic"):
            param = "Parameters/Basic"
        else:
            param = "Parameters/Base"
        episode_url = f"https://static1.matific.com/content/episodes/{folder}/index.html?parameters={param}&usability=true&geographicLocale=BRA"

        ua = self.fp["user-agent"]
        platform_str = "Windows" if "Windows" in ua else ("Mac" if "Mac" in ua else "Linux")
        scoring_path = f"https://www.matific.com/students/episode-container/3.8.5/episode-container.html?source_view=webApp&app_version={self.app_version}&platform=WebGLPlayer&device_model=Chrome+{self.chrome_version}&operating_system=Unknown+OS+Unknown+OS+Version"

        update_status("Inicializando o aplicativo Matific...", 2)

        await self.send_ping()
        await sleep_loading(0.1, 0.4)

        await self.send_tracking_event("GamePageLoad", 25, None, None, {
            "browser": f"Chrome {self.chrome_version.split('.')[0]}",
            "is_lite": False,
            "browser_version": self.fp["user-agent"],
            "machine_platform": platform_str,
            "version_after_no_cache_speedtest": None
        })
        await sleep_loading(0.2, 0.5)

        await self.send_tracking_event("UnityInitStart", 27, None, None, {
            "browser": f"Chrome {self.chrome_version.split('.')[0]}",
            "is_lite": False,
            "browser_version": self.fp["user-agent"],
            "machine_platform": platform_str
        })

        asset_task = asyncio.create_task(self._simulate_asset_loading())
        await sleep_loading(0.2, 0.5)

        await self.send_tracking_event("UnityWasmLoaded", 28, None, None, {
            "browser": f"Chrome {self.chrome_version.split('.')[0]}",
            "is_lite": False,
            "browser_version": self.fp["user-agent"],
            "machine_platform": platform_str,
            "path": f"https://site1.matific.com/students/app/{self.app_version}/Build/ProductionWebGL.wasm.br"
        })
        await self.send_tracking_event("UnityDataLoaded", 29, None, None, {
            "browser": f"Chrome {self.chrome_version.split('.')[0]}",
            "is_lite": False,
            "browser_version": self.fp["user-agent"],
            "machine_platform": platform_str
        })
        for prog in ["25", "50", "75", "100"]:
            await self.send_tracking_event("UnityLoadProgress", 24, None, None, {
                "browser": f"Chrome {self.chrome_version.split('.')[0]}",
                "is_lite": False,
                "browser_version": self.fp["user-agent"],
                "machine_platform": platform_str,
                "progress": prog
            })
            await sleep_loading(0.1, 0.3)

        await self.send_tracking_event("UnityLoadCompleted", 23, None, None, {
            "browser": f"Chrome {self.chrome_version.split('.')[0]}",
            "is_lite": False,
            "browser_version": self.fp["user-agent"],
            "machine_platform": platform_str,
            "caching": {"wasm_cached_in_browser": "unknown", "data_cached_in_browser": "unknown", "framework_cached_in_browser": False}
        })
        await asset_task
        await sleep_loading(0.3, 0.8)

        session_start_ms = int(time.time() * 1000)
        _login_stop = asyncio.Event()
        _login_task = None
        _live_class_id = None
        game_state = {}

        try:
            _ = await self.get_init_data()
            await self.generate_firebase_token()
            await self.get_firebase_config()
            await self.exchange_firebase_token()
            _live_class_id = (self.init_data or {}).get("UserData", {}).get("ClassId")
            if _live_class_id and self.firebase_id_token:
                await self._send_live_class_login(_live_class_id, session_start_ms)
                _login_task = asyncio.create_task(self._live_class_login_loop(_live_class_id, session_start_ms, _login_stop))
            game_state = await self.fetch_game_state(campaign_ids=[campaign_id] if campaign_id else [])
        except Exception as e:
            logger.warning(f"[MATIFIC-PLAY] Init warning: {e}")

        batch_1 = [
            {"event_name": "screen_view", "event_enum": 16, "flow_run_id": None, "app_run_id": app_run_id, "data": {"screenname": "SplashScreen"}},
            {"event_name": "ScreenViewLoaded", "event_enum": 21, "flow_run_id": None, "app_run_id": app_run_id, "data": {"screenname": "SplashScreen", "time_from_init": random.uniform(1.0, 2.0)}},
            {"event_name": "InitDataAttempt", "event_enum": 1, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {}},
            {"event_name": "InitDataParsingSuccess", "event_enum": 3, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.1, 0.3)}},
            {"event_name": "GameStateFetchAttempt", "event_enum": 6, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {}},
            {"event_name": "GameStateReceived", "event_enum": 7, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.2, 0.4)}},
            {"event_name": "GameStatePopulated", "event_enum": 8, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.05, 0.15)}},
            {"event_name": "MandatoryAssetsFetchAttempt", "event_enum": 12, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {}},
            {"event_name": "EpisodesEnrichmentFetchAttempt", "event_enum": 33, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {}},
            {"event_name": "MandatoryAssetsFetchCompleted", "event_enum": 13, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.1, 0.3)}}
        ]
        await self.send_tracking_events_batch(batch_1)
        await sleep_loading(0.3, 0.8)

        batch_2 = [
            {"event_name": "EpisodesEnrichmentSuccess", "event_enum": 34, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.1, 0.3)}},
            {"event_name": "LoadingAvatarSkins", "event_enum": 14, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.05, 0.15)}},
            {"event_name": "InitDataPopulationSuccess", "event_enum": 18, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(0.05, 0.15)}},
            {"event_name": "AppInitComplete", "event_enum": 15, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "data": {"duration": random.uniform(1.0, 2.0)}},
            {"event_name": "screen_view", "event_enum": 16, "flow_run_id": None, "app_run_id": app_run_id, "data": {"screenname": "MainMap"}}
        ]
        await self.send_tracking_events_batch(batch_2)
        await sleep_loading(0.3, 0.8)

        update_status("Carregando jogo...", 5)
        await self.send_tracking_event("EpisodeInvoked", 59, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
        })
        await self.send_tracking_event("EpisodeClicked", 50, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
            "episode_icon_click_state": "Enabled",
        })
        await self.send_tracking_event("screen_view", 16, None, app_run_id, {"screenname": "LoadingEpisode"})
        await self.send_tracking_event("EpisodeDetailsSentToContainer", 53, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
        })
        await self.send_tracking_event("EpisodeLoadingShown", 52, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
        })
        await self.send_tracking_event("EpisodeOpen", 51, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
        })

        try:
            gdp_url = f"https://prod-scoringservice.matific.com/gameDataPersistence?user_data_token={self.user_data_token}&episode_id={episode_id}&assignment_id={assignment_id}&context={context_id}&episode_instance_id={episode_instance_id}"
            await self.client.get(gdp_url, headers=self.headers)
        except Exception:
            pass

        episode_start_ms = int(time.time() * 1000)

        start_fact = {
            "type": "StartEpisode",
            "origin_id": origin_id,
            "episode_slug": slug,
            "channel": "Website",
            "is_offline_fact": False,
            "episode_type": "Worksheet",
            "envelope_version": "3.8.5",
            "activity_context": context_id,
            "assignment_type": 4,
            "assignment_id": assignment_id,
            "is_auto_assigned": 0,
            "episode_instance_id": episode_instance_id,
            "app_version": self.app_version,
            "campaign_id": campaign_id,
            "subject": 0,
            "platform": "WebGLPlayer",
            "is_accessible": False,
            "dev_name": dev_name,
            "problem_count": problem_count,
            "ran_in_adaptive_mode": False,
            "no_progress_bar_in_envelope": False,
            "episode_run_discriminator": episode_run_discriminator,
            "episode_name": dev_name,
            "episode_version": "47.601",
            "since_episode_start_sec": random.randint(30, 70),
            "is_arena": False,
            "path": scoring_path,
            "client_time": int(time.time() * 1000),
            "time_diff": 0,
            "from_tablet": False
        }
        await self.send_scoring_fact(start_fact)

        answers_list = [""] * problem_count
        if _live_class_id and self.firebase_id_token:
            try:
                await self._send_live_class_episode_results(_live_class_id, episode, origin_id, "StartEpisode", answers_list, problem_count, episode_start_ms)
            except Exception:
                pass

        problem_ids = []
        for idx in range(problem_count):
            cache_key = (slug, idx)
            if cache_key not in _PROBLEM_ID_CACHE:
                _PROBLEM_ID_CACHE[cache_key] = uuid.uuid4().hex
            problem_ids.append(_PROBLEM_ID_CACHE[cache_key])

        if target_accuracy == "realistic":
            mistakes_map = [0] * problem_count
            if random.random() >= 0.7:
                num_missed = random.choice([1, 2])
                missed_indices = random.sample(range(problem_count), min(num_missed, problem_count))
                for idx in missed_indices:
                    mistakes_map[idx] = 1
        elif target_accuracy == "perfect":
            mistakes_map = [0] * problem_count
        else:
            mistakes_map = [random.choice([0, 1]) for _ in range(problem_count)]

        correct_count = 0
        for i in range(problem_count):
            if i > 0 and i % 2 == 0:
                await self.send_ping()
            problem_start_time = time.time()
            update_status(f"Resolvendo questão {i+1} de {problem_count}...", int(10 + (i / problem_count) * 75))

            intro_fact = {
                **start_fact,
                "type": "PresentProblemIntro",
                "problem_index": i,
                "index": i,
                "step": 0,
                "problem_id": problem_ids[i],
                "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
                "since_question_start_sec": int(time.time() - problem_start_time),
                "client_time": int(time.time() * 1000),
            }
            await self.send_scoring_fact(intro_fact)
            await sleep_loading(0.5, 1.2)

            num_mistakes = mistakes_map[i]
            if num_mistakes > 0:
                for attempt in range(1, num_mistakes + 1):
                    s_min = float(timings.get("struggle_min", 2.0))
                    s_max = float(timings.get("struggle_max", 5.0))
                    await asyncio.sleep(random.uniform(s_min, s_max))

                    wrong_fact = {
                        **start_fact,
                        "type": "SubmitSolution",
                        "problem_index": i,
                        "step_count": 1,
                        "step_index": 0,
                        "attempt": attempt,
                        "mistakes": attempt,
                        "is_correct": 0,
                        "problem_id": problem_ids[i],
                        "since_question_start_sec": int(time.time() - problem_start_time),
                        "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
                        "client_time": int(time.time() * 1000),
                    }
                    await self.send_scoring_fact(wrong_fact)
                    answers_list[i] = {"attempts": attempt, "correct": 0, "index": i, "step_attempts": attempt, "step_count": 1}
                    if _live_class_id and self.firebase_id_token:
                        try:
                            await self._send_live_class_episode_results(_live_class_id, episode, origin_id, "SubmitSolution", answers_list, problem_count, episode_start_ms)
                        except Exception:
                            pass

                c_min = float(timings.get("correction_min", 1.5))
                c_max = float(timings.get("correction_max", 3.0))
                await asyncio.sleep(random.uniform(c_min, c_max))

            sol_min = float(timings.get("solving_min", 2.0))
            sol_max = float(timings.get("solving_max", 5.0))
            await asyncio.sleep(random.uniform(sol_min, sol_max))

            correct_fact = {
                **start_fact,
                "type": "SubmitSolution",
                "problem_index": i,
                "step_count": 1,
                "step_index": 0,
                "attempt": num_mistakes + 1,
                "mistakes": num_mistakes,
                "is_correct": 1,
                "problem_id": problem_ids[i],
                "since_question_start_sec": int(time.time() - problem_start_time),
                "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
                "client_time": int(time.time() * 1000),
            }
            await self.send_scoring_fact(correct_fact)
            correct_count += 1

            answers_list[i] = {"attempts": num_mistakes + 1, "correct": 1, "index": i, "step_attempts": num_mistakes + 1, "step_count": 1}
            if _live_class_id and self.firebase_id_token:
                try:
                    await self._send_live_class_episode_results(_live_class_id, episode, origin_id, "SubmitSolution", answers_list, problem_count, episode_start_ms)
                except Exception:
                    pass

            if i < problem_count - 1:
                iq_min = float(timings.get("inter_question_min", 0.5))
                iq_max = float(timings.get("inter_question_max", 1.5))
                await asyncio.sleep(random.uniform(iq_min, iq_max))

        update_status("Finalizando tarefa...", 90)
        await sleep_loading(1.0, 2.0)

        points = correct_count * 20
        finish_fact = {
            **start_fact,
            "type": "FinishEpisode",
            "score": correct_count,
            "points": points,
            "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
            "episode_duration": int(time.time() * 1000) - episode_start_ms,
            "client_time": int(time.time() * 1000),
        }
        await self.send_scoring_fact(finish_fact)

        if _live_class_id and self.firebase_id_token:
            try:
                await self._send_live_class_episode_results(_live_class_id, episode, origin_id, "FinishEpisode", answers_list, problem_count, episode_start_ms)
            except Exception:
                pass

        await self.send_tracking_event("ContainerReportedUserFinished", 55, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
        })
        await sleep_loading(0.5, 1.0)
        await self.send_tracking_event("EpisodePostScreenUserAction", 57, flow_run_id, app_run_id, {
            "ep_id": episode_id,
            "activity_context": int(context_id),
            "invoke_method": "UserClick",
            "episode_url": episode_url,
        })

        try:
            user_state = game_state.get("user_state", [])
            if user_state:
                ranking_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.RankingData"), None)
                currency_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.CurrencyData"), None)
                weekly_goal_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.UserGoalProgressData" and r.get("item_id") == "weekly_goal"), None)

                post_rows = []
                if ranking_row:
                    ranking_data = ranking_row.get("data", {}).copy()
                    ranking_data["currentXp"] = ranking_data.get("currentXp", 0) + 20
                    ranking_data["currentRank"] = (ranking_data["currentXp"] // 100) + 1
                    post_rows.append({
                        "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                        "table_name": "user_state",
                        "row_id": ranking_row["row_id"],
                        "data_version_number": 0,
                        "object_type": "Matific.Mad.RankingData",
                        "data": ranking_data,
                        "deprecation_rule": None,
                        "item_id": ranking_row.get("item_id")
                    })
                if weekly_goal_row:
                    weekly_data = weekly_goal_row.get("data", {}).copy()
                    dur_s = int((time.time() * 1000 - episode_start_ms) / 1000)
                    weekly_data["progress"] = weekly_data.get("progress", 0) + dur_s
                    weekly_data["lastProgressDate"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if weekly_data["progress"] >= 1800:
                        weekly_data["isCompleted"] = True
                    post_rows.append({
                        "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                        "table_name": "user_state",
                        "row_id": weekly_goal_row["row_id"],
                        "data_version_number": 0,
                        "object_type": "Matific.Mad.UserGoalProgressData",
                        "data": weekly_data,
                        "deprecation_rule": None,
                        "item_id": weekly_goal_row.get("item_id")
                    })
                if currency_row:
                    currency_data = currency_row.get("data", {}).copy()
                    currency_data["currentCoins"] = currency_data.get("currentCoins", 0) + (correct_count * 25)
                    post_rows.append({
                        "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                        "table_name": "user_state",
                        "row_id": currency_row["row_id"],
                        "data_version_number": 0,
                        "object_type": "Matific.Mad.CurrencyData",
                        "data": currency_data,
                        "deprecation_rule": None,
                        "item_id": currency_row.get("item_id")
                    })
                if post_rows:
                    await self.store_game_state(post_rows)
        except Exception as e:
            logger.warning(f"[MATIFIC-PLAY] Post-episode store warning: {e}")

        try:
            row_to_send = {
                "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                "table_name": "game_entity",
                "row_id": str(uuid.uuid4()),
                "data_version_number": 0,
                "object_type": "Matific.Mad.EpisodeStorableData",
                "data": {
                    "$type": "Matific.Mad.EpisodeStorableData, AssetsAssembly",
                    "wasPassed": True,
                    "wasSkipped": False
                },
                "deprecation_rule": None,
                "item_id": None,
                "entity_id": episode_id,
                "instance_id": str(uuid.uuid4()),
                "order": 0,
                "zone": 0,
                "highest_score": correct_count,
                "last_score": correct_count,
                "number_of_plays": 1,
            }
            await self.store_game_state([row_to_send])
        except Exception as e:
            logger.warning(f"[MATIFIC-PLAY] EpisodeStorableData persistence warning: {e}")

        _login_stop.set()
        if _login_task and not _login_task.done():
            _login_task.cancel()
            try:
                await _login_task
            except asyncio.CancelledError:
                pass

        update_status("Concluído com sucesso!", 100)
        logger.info(f"[MATIFIC-PLAY] Episode {slug} completed. Score={correct_count}/{problem_count}")
        return True
