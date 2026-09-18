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

# Cache for per-episode static metadata: (slug, episode_id) -> {dev_name, episode_name, episode_version, problem_count, episode_url}
_EPISODE_META_CACHE: dict[tuple[str, str], dict] = {}
_EPISODE_DATA_CACHE: Optional[dict] = None

_KNOWN_SLUG_SUFFIXES = ("Advanced", "Basic", "Main")


def _split_slug(slug: str) -> tuple[str, str]:
    """Split a Matific slug into (dev_name, param_suffix).

    Real scoring facts strip the trailing Main/Basic/Advanced from dev_name
    and use it as Parameters/<suffix> in the episode URL. E.g.
    WorksheetProbabilityPossibleMain -> (WorksheetProbabilityPossible, Main).
    Slugs without a known suffix use Parameters/Base.
    """
    if not slug:
        return "", "Base"
    for suffix in _KNOWN_SLUG_SUFFIXES:
        if slug.endswith(suffix) and len(slug) > len(suffix):
            return slug[: -len(suffix)], suffix
    return slug, "Base"

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
        # Real SalaDoFuturo frontend sends RA+digito+UF without zero-padding
        # (e.g. "1234567890SP"), same as app.py /api/login.
        constructed_user = f"{self.ra}{self.digito}{self.uf}"
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

    async def get_episode_static_meta(self, slug: str, episode_id: Optional[str] = None) -> dict:
        """Fetch per-episode static metadata (dev_name, version, problem_count, url).

        Sources (observed in real browser HAR):
        - prod-static-web1 episode_data Mathematics/default/{curriculum}.json maps
          episode Id -> {Name, Slug, Url (with index$hash + Parameters/...)}.
          The curriculum id is reused from init_data EpisodeEnrichmentUrl
          (.../by_topic/default/{curriculum}.json).
        - static1 episode-all$hash.js.gz contains
          var episodeDescriptor={"type":"Episode","version":"155.24",
          "name":"WorksheetProbabilityPossible",...} and the MainSlides
          QUESTION slides whose count equals scoring problem_count.

        Results are cached per (slug, episode_id). On any failure returns
        heuristic values derived from the slug so scoring can still proceed.
        """
        global _EPISODE_DATA_CACHE
        cache_key = (slug or "", episode_id or "")
        if cache_key in _EPISODE_META_CACHE:
            return _EPISODE_META_CACHE[cache_key]

        dev_name, param = _split_slug(slug or "")
        fallback = {"dev_name": dev_name, "episode_name": dev_name,
                    "episode_version": None, "problem_count": None,
                    "episode_url": None, "parameters": f"Parameters/{param}"}
        try:
            if not self.init_data:
                await self.get_init_data()
            enrich_url = (self.init_data or {}).get("Urls", {}).get("EpisodeEnrichmentUrl", "")
            m = re.search(r"/episode_data/bra/pt-br/by_topic/default/([^/]+)\.json", enrich_url or "")
            curriculum = m.group(1) if m else "c6f70b1f-e3d5-46e5-9541-3d22e571f3eb"
            if _EPISODE_DATA_CACHE is None:
                data_url = f"https://prod-static-web1.matific.com/episode_data/bra/pt-br/Mathematics/default/{curriculum}.json"
                try:
                    resp = await self.client.get(data_url, headers={"Accept": "*/*", "Referer": "https://www.matific.com/", **self.headers})
                    _EPISODE_DATA_CACHE = resp.json() if resp.status_code == 200 else {}
                except Exception:
                    _EPISODE_DATA_CACHE = {}
            entry = None
            if isinstance(_EPISODE_DATA_CACHE, dict):
                if episode_id and episode_id in _EPISODE_DATA_CACHE:
                    entry = _EPISODE_DATA_CACHE[episode_id]
                else:
                    for v in _EPISODE_DATA_CACHE.values():
                        if isinstance(v, dict) and v.get("Slug") == slug:
                            entry = v
                            break
            ep_url = (entry or {}).get("Url") if entry else None
            if entry and entry.get("Name"):
                fallback["dev_name"] = entry["Name"]
                fallback["episode_name"] = entry["Name"]
            if ep_url:
                fallback["episode_url"] = ep_url
                if (entry or {}).get("ParametersPath"):
                    fallback["parameters"] = entry["ParametersPath"]
                else:
                    pm = re.search(r"parameters=([^&]+)", ep_url)
                    if pm:
                        fallback["parameters"] = urllib.parse.unquote(pm.group(1))
            # Fetch episode-all JS to get version + problem_count
            if ep_url:
                base = ep_url.split("index$")[0] if "index$" in ep_url else None
                hm = re.search(r"index\$(\d+)\.html", ep_url)
                if base and hm:
                    js_url = f"{base}episode-all${hm.group(1)}.js.gz?cb={int(time.time())}"
                    try:
                        rjs = await self.client.get(js_url, headers={"Accept": "*/*", "Referer": "https://www.matific.com/", **self.headers})
                        if rjs.status_code == 200:
                            txt = rjs.text if hasattr(rjs, "text") else ""
                            vm = re.search(r'var episodeDescriptor=\{[^}]*?"version":"([^"]+)"[^}]*?"name":"([^"]+)"', txt)
                            if vm:
                                fallback["episode_version"] = vm.group(1)
                                fallback["dev_name"] = vm.group(2)
                                fallback["episode_name"] = vm.group(2)
                            else:
                                vm2 = re.search(r'"classname":"SlidesEpisode"[^}]{0,300}?"version":"([^"]+)"', txt)
                                vm3 = re.search(r'episodeDescriptor.{0,500}?"version"\s*:\s*"([^"]+)"', txt)
                                vm4 = re.search(r'"name"\s*:\s*"([A-Z][A-Za-z0-9]+)"[^}]{0,300}?"classname"\s*:\s*"SlidesEpisode"', txt)
                                if vm2:
                                    fallback["episode_version"] = vm2.group(1)
                                elif vm3:
                                    fallback["episode_version"] = vm3.group(1)
                                if vm4:
                                    fallback["dev_name"] = vm4.group(1)
                                    fallback["episode_name"] = vm4.group(1)
                            # problem_count = number of QUESTION slides (5 for the HAR example)
                            qcount = len(re.findall(r'"slideType":"QUESTION"', txt))
                            if qcount > 0:
                                fallback["problem_count"] = qcount
                    except Exception as e:
                        logger.debug(f"[MATIFIC-META] episode-all fetch warning: {e}")
        except Exception as e:
            logger.debug(f"[MATIFIC-META] static meta warning: {e}")

        _EPISODE_META_CACHE[cache_key] = fallback
        return fallback

    def _tracking_base(self) -> dict:
        """Build the shared tracking-event envelope observed in the real HAR."""
        ud = (self.init_data or {}).get("UserData", {}) if isinstance(self.init_data, dict) else {}
        return {
            "zone": "AssignedMap",
            "consumer_type": ud.get("ConsumerType") or "B2B",
            "grade_code": ud.get("GradeCode") or ud.get("LearningLevel") or "G8",
            "region": ud.get("Region") or "BRA",
            "language": ud.get("Locale") or "f8f18c08-442c-4166-8e09-c8ef72803a70",
            "school_id": ud.get("SchoolId") or "",
            "teacher_language": (ud.get("TeacherLanguageCode") or "pt-br"),
            "teacher_region": (ud.get("TeacherRegionCode") or "BRA"),
            "user_type": ud.get("UserType") or "ClassStudent",
        }

    async def send_keep_alive(self) -> bool:
        """Mirror browser POST /api/v2/interactions/keep-alive/ {"USER_ACTIVE":true}."""
        url = "https://www.matific.com/api/v2/interactions/keep-alive/"
        headers = {
            "X-CSRFToken": self.csrftoken or "",
            "Referer": f"https://www.matific.com/students/app/{self.app_version}/",
            **self.headers,
        }
        try:
            resp = await self.client.post(url, json={"USER_ACTIVE": True}, headers=headers)
            return resp.status_code == 200
        except Exception:
            return False

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
        base = self._tracking_base()
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
                **base,
                "data": {
                    "event_name": event_name,
                    "browser": f"Chrome/{self.chrome_version}",
                    **data
                }
            }
            # Per-event zone override (e.g. LoadingEpisode, PostEpisode)
            if ev.get("zone"):
                payload["zone"] = ev["zone"]

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
        # Core Unity WebGL shell (mirrors HAR idx002-041: loader, framework,
        # data, utils, episode-container scripts, firebase SDKs, settings).
        base = f"https://site1.matific.com/students/app/{self.app_version}"
        www = f"https://www.matific.com/students/app/{self.app_version}"
        assets = [
            f"{base}/Build/ProductionWebGL.loader.js",
            f"{base}/Build/ProductionWebGL.framework.js.br",
            f"{base}/Build/ProductionWebGL.data.br",
            f"{base}/StreamingAssets/aa/WebGL/bundle_all.bundle",
            f"{base}/StreamingAssets/aa/catalog.json",
            f"{www}/utils.js",
            f"{www}/unity-webview.js",
            f"{www}/custom-scripts.js",
            f"{www}/events-tracker.js",
            f"{www}/StreamingAssets/aa/settings.json",
            f"{www}/StreamingAssets/aa/catalog.bin",
            "https://www.gstatic.com/firebasejs/8.2.4/firebase-app.js",
            "https://www.gstatic.com/firebasejs/8.2.4/firebase-auth.js",
            "https://www.gstatic.com/firebasejs/8.2.4/firebase-firestore.js",
            "https://www.matific.com/students/episode-container/3.8.5/scripts/jquery-3.6.0.min.js",
            "https://www.matific.com/students/episode-container/3.8.5/dist/episode-controller.app.min.js",
            "https://www.matific.com/students/episode-container/3.8.5/dist/matific-firestore.lib.min.js",
        ]
        sem = asyncio.Semaphore(6)

        async def _get(u):
            async with sem:
                try:
                    await self.client.get(u, headers={"Accept": "*/*", "Referer": f"https://www.matific.com/students/app/{self.app_version}/", **self.headers})
                except Exception:
                    pass

        await asyncio.gather(*[_get(a) for a in assets], return_exceptions=True)

    async def _simulate_episode_content_loading(self, episode_url: str):
        """Fetch the episode runtime content (infra libs + episode bundles).

        Mirrors HAR idx149-159: libs.js.gz, slate, episode-all$hash,
        localization$hash, CommonAudio/AfterSolution audio packs, fonts,
        shaders. These are CDN fetches (unauthenticated) but a strict client
        loads them before PresentProblemIntro; fetching them keeps timing and
        traffic shape realistic.
        """
        try:
            urls = [
                "https://static1.matific.com/content/infra/2.31/libs/libs.js.gz",
                "https://static2.matific.com/content/infra/2.31/libs/slate-2.31.js.gz",
                "https://static1.matific.com/content/infra/2.31/res/fonts/Infra_Latin.fonts.jsonp.gz",
                "https://static1.matific.com/content/infra/2.31/res/assets3d/shaders.jsonp.gz",
                "https://static1.matific.com/content/infra/2.31/res/audio/AfterSolution/AudioPackageAfterSolution0.mp3.jsonp.gz",
                "https://static1.matific.com/content/infra/2.31/res/audio/CommonAudio/AudioPackageCommonAudio0.mp3.jsonp.gz",
                "https://static1.matific.com/content/infra/2.31/res/audio/EndScreen/AudioPackageEndScreen0.mp3.jsonp.gz",
            ]
            if episode_url and "index$" in episode_url:
                base = episode_url.split("index$")[0]
                m = re.search(r"index\$(\d+)\.html", episode_url)
                if base and m:
                    h = m.group(1)
                    # folder is the path segment between /episodes/ and /index$
                    urls.insert(2, f"{base}episode-all${h}.js.gz")
                    try:
                        folder = episode_url.split("/content/episodes/")[1].split("/index$")[0]
                        urls.insert(3, f"https://static2.matific.com/content/episodes/{folder}/localization${h}.js.gz")
                    except Exception:
                        pass
            sem = asyncio.Semaphore(4)

            async def _get(u):
                async with sem:
                    try:
                        await self.client.get(u, headers={"Accept": "*/*", "Referer": "https://www.matific.com/", **self.headers})
                    except Exception:
                        pass

            await asyncio.gather(*[_get(u) for u in urls], return_exceptions=True)
        except Exception:
            pass

    async def _fetch_supporting_data(self):
        """Fetch read-only supporting JSONs the real client loads on the map.

        Mirrors HAR idx082-087/113: episode_data, grade mapping, translations,
        countries, domains-scores, user assignments, leaderboard. All small
        except episode_data (served from cache by get_episode_static_meta).
        Failures are non-fatal.
        """
        try:
            ud = (self.init_data or {}).get("UserData", {}) if isinstance(self.init_data, dict) else {}
            headers = {"Accept": "*/*", "Referer": "https://www.matific.com/", **self.headers}
            urls = [
                "https://prod-static-web1.matific.com/translate_episodes/portuguese_br.json",
                f"https://www.matific.com/students/translations/pt-BR/vo/active_keys.json",
                "https://site1.matific.com/home/api/countries/",
                "https://www.matific.com/api/student-site-v2/game-user-assignments/?subject=0",
                "https://www.matific.com/api/student-site-v2/get-user-type/",
            ]
            grade = ud.get("GradeCode") or ud.get("LearningLevel") or "G8"
            gnum = str(grade).lstrip("G") or "8"
            locale = ud.get("Locale") or "f8f18c08-442c-4166-8e09-c8ef72803a70"
            curriculum = "c6f70b1f-e3d5-46e5-9541-3d22e571f3eb"
            try:
                enrich = ((self.init_data or {}).get("Urls", {}) or {}).get("EpisodeEnrichmentUrl", "")
                mm = re.search(r"/default/([^/]+)\.json", enrich or "")
                if mm:
                    curriculum = mm.group(1)
            except Exception:
                pass
            urls.append(f"https://prod-static-web1.matific.com/episode_data/bra/pt-br/Mathematics/grade_episodes_mapping/default/{curriculum}.json")
            urls.append(f"https://www.matific.com/cached-api/topics/get-domains-scores/{locale}/{locale}/{curriculum}/8/{gnum}?subject=0")
            urls.append(f"https://prod-madgames2fetch.matific.com/?platform=WebGLPlayer&app_version={self.app_version}&data_version=0&type=fetch_leaderboard_data&is_login=True")
            sem = asyncio.Semaphore(4)

            async def _get(u):
                async with sem:
                    try:
                        await self.client.get(u, headers=headers)
                    except Exception:
                        pass

            await asyncio.gather(*[_get(u) for u in urls], return_exceptions=True)
        except Exception:
            pass

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


    async def send_scoring_facts(self, facts: list) -> bool:
        """Send multiple scoring facts in a single addFacts call (e.g. EpisodeEngagement x2)."""
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
            "facts": facts
        }
        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            if resp.status_code in (401, 403):
                if await self.authenticate():
                    payload["user_data_token"] = self.user_data_token
                    resp = await self.client.post(url, json=payload, headers=headers)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[MATIFIC-SCORING] Scoring facts error: {e}")
            return False

    async def complete_episode(self, episode: dict, target_accuracy: str = "realistic", on_progress=None, timings: dict = None) -> bool:
        """Simulate playing an episode end-to-end, replicating the real browser flow.

        Field-level spec reverse-engineered from harfiles/matific_after.har
        (School assignment WorksheetProbabilityPossibleMain, 5 problems):
        - scoring facts carry NO campaign_id; assignment_type=1 and
          activity_context="1" for School (licao de classe); dev_name/episode_name
          strip the trailing Main/Basic/Advanced; episode_version and problem_count
          come from the episode static content; discriminator is YYYYMMDD_16chars.
        - PresentProblemIntro has no problem_count (and no since_question on i==0);
          SubmitSolution/FinishEpisode include problem_count; FinishEpisode score is
          first-try correct count with points=score*20, plus EpisodeEngagement x2.
        - Firestore live-class only receives Login docs (no episode-results docs).
        """
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
        episode_run_discriminator = time.strftime("%Y%m%d") + "_" + "".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=16))

        slug = episode["slug"]
        assignment_id = episode.get("assignment_id")
        campaign_id = episode.get("campaign_id")
        episode_id = episode.get("episode_id")

        # --- assignment_type / activity_context (critical for School completion) ---
        assignment_type = episode.get("assignment_type")
        activity_context = episode.get("activity_context", episode.get("context_id"))
        source = str(episode.get("source") or "")
        if assignment_type is None:
            if "Campanha" in source or "campaign" in source.lower():
                assignment_type = 4
            else:
                assignment_type = 1
        try:
            assignment_type_int = int(assignment_type)
        except Exception:
            assignment_type_int = 1
        if activity_context is None:
            activity_context = "13" if assignment_type_int == 4 else "1"
        activity_context = str(activity_context)
        if assignment_type_int == 1 and activity_context == "13":
            activity_context = "1"
        context_id = activity_context
        context_id_int = int(activity_context) if str(activity_context).isdigit() else 1

        # --- static per-episode metadata (version, problem_count, url) ---
        meta = {}
        try:
            meta = await self.get_episode_static_meta(slug, episode_id)
        except Exception:
            meta = {}
        dev_name = meta.get("dev_name") or _split_slug(slug)[0]
        episode_name = meta.get("episode_name") or dev_name
        episode_version = meta.get("episode_version") or "47.601"
        problem_count = meta.get("problem_count") or episode.get("problem_count", 5) or 5
        try:
            problem_count = int(problem_count)
        except Exception:
            problem_count = 5
        parameters = meta.get("parameters") or f"Parameters/{_split_slug(slug)[1]}"
        episode_url = meta.get("episode_url")
        if not episode_url:
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', dev_name)
            folder = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
            episode_url = f"https://static1.matific.com/content/episodes/{folder}/index.html?parameters={parameters}&usability=true&geographicLocale=BRA"

        episode_instance_id = str(uuid.uuid4())

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
            try:
                await self.send_keep_alive()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[MATIFIC-PLAY] Init warning: {e}")

        batch_1 = [
            {"event_name": "screen_view", "event_enum": 16, "flow_run_id": None, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"screenname": "SplashScreen"}},
            {"event_name": "ScreenViewLoaded", "event_enum": 21, "flow_run_id": None, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"screenname": "SplashScreen", "time_from_init": random.uniform(1.0, 2.0)}},
            {"event_name": "InitDataAttempt", "event_enum": 1, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {}},
            {"event_name": "InitDataParsingSuccess", "event_enum": 3, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.1, 0.3)}},
            {"event_name": "GameStateFetchAttempt", "event_enum": 6, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {}},
            {"event_name": "GameStateReceived", "event_enum": 7, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.2, 0.4)}},
            {"event_name": "GameStatePopulated", "event_enum": 8, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.05, 0.15)}},
            {"event_name": "MandatoryAssetsFetchAttempt", "event_enum": 12, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {}},
            {"event_name": "EpisodesEnrichmentFetchAttempt", "event_enum": 33, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {}},
            {"event_name": "MandatoryAssetsFetchCompleted", "event_enum": 13, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.1, 0.3)}}
        ]
        await self.send_tracking_events_batch(batch_1)
        await sleep_loading(0.3, 0.8)

        batch_2 = [
            {"event_name": "EpisodesEnrichmentSuccess", "event_enum": 34, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.1, 0.3)}},
            {"event_name": "LoadingAvatarSkins", "event_enum": 14, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.05, 0.15)}},
            {"event_name": "InitDataPopulationSuccess", "event_enum": 18, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(0.05, 0.15)}},
            {"event_name": "AppInitComplete", "event_enum": 15, "flow_run_id": init_flow_run_id, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"duration": random.uniform(1.0, 2.0)}},
            {"event_name": "screen_view", "event_enum": 16, "flow_run_id": None, "app_run_id": app_run_id, "zone": "SplashScreen", "data": {"screenname": "MainMap"}}
        ]
        await self.send_tracking_events_batch(batch_2)
        await sleep_loading(0.3, 0.8)

        # Map navigation flow (mirrors HAR idx121-140): MainMap -> AssignedWork
        # -> AssignedMap, loading supporting JSONs in parallel like the client.
        update_status("Carregando mapa de atividades...", 4)
        support_task = asyncio.create_task(self._fetch_supporting_data())
        await self.send_tracking_events_batch([
            {"event_name": "screen_view", "event_enum": 16, "flow_run_id": None, "app_run_id": app_run_id, "zone": "MainMap", "data": {"screenname": "AssignedWork"}},
            {"event_name": "ScreenViewLoaded", "event_enum": 21, "flow_run_id": None, "app_run_id": app_run_id, "zone": "AssignedWork", "data": {"screen_name": "AssignedWork", "load_time_in_seconds": round(random.uniform(2.0, 3.2), 3)}},
        ])
        await sleep_loading(0.4, 0.9)
        await self.send_tracking_events_batch([
            {"event_name": "screen_view", "event_enum": 16, "flow_run_id": None, "app_run_id": app_run_id, "zone": "AssignedWork", "data": {"screenname": "AssignedMap"}},
            {"event_name": "ScreenViewLoaded", "event_enum": 21, "flow_run_id": None, "app_run_id": app_run_id, "zone": "AssignedMap", "data": {"screen_name": "AssignedMap", "load_time_in_seconds": round(random.uniform(2.0, 3.0), 3)}},
        ])
        await support_task
        try:
            await self.send_keep_alive()
        except Exception:
            pass
        await sleep_loading(0.2, 0.6)

        # Shared episode telemetry object (mirrors real EpisodeInvoked payload)
        ud = (self.init_data or {}).get("UserData", {}) if isinstance(self.init_data, dict) else {}
        try:
            grade_int = int(str(ud.get("GradeCode") or ud.get("LearningLevel") or "G8").lstrip("G"))
        except Exception:
            grade_int = 8
        student_uuid = ud.get("Id") or self.slatemath_user_id or ""
        ep_title = episode.get("title") or translate_matific_slug(slug)
        ep_subtitle = episode.get("subtitle") or ""
        episode_obj = {
            "EpisodeId": episode_id,
            "Zone": 1,
            "Subject": 0,
            "AssignedToAll": True,
            "IsAutoAssignment": False,
            "AssignmentId": assignment_id,
            "AssignmentUniqueId": f"{assignment_id}_{episode_id}",
            "WasSkipped": False,
            "LastScore": 0,
            "HighestScore": 0,
            "NumberOfPlays": 1,
            "PreviousHighestNumberOfStars": -1,
            "EpisodeState": 3,
            "ThumbnailUrl": f"https://static1.matific.com/v1/346x242/{slug}.png",
            "Title": ep_title,
            "SubTitle": ep_subtitle,
            "IsLearnNow": False,
            "EntityType": 0,
            "Order": episode.get("order") or 2,
            "WasPassed": False,
            "InstanceId": episode_instance_id,
        }

        update_status("Carregando jogo...", 5)
        await self.send_tracking_event("EpisodeInvoked", 59, flow_run_id, app_run_id, {
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })
        await self.send_tracking_event("EpisodeClicked", 50, flow_run_id, app_run_id, {
            "episode_icon_click_state": 0,
            "skin_name": None,
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })
        await self.send_tracking_event("screen_view", 16, None, app_run_id, {"screenname": "LoadingEpisode"})
        await self.send_tracking_event("EpisodeDetailsSentToContainer", 53, flow_run_id, app_run_id, {
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })
        await self.send_tracking_event("EpisodeLoadingShown", 52, flow_run_id, app_run_id, {
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })
        await self.send_tracking_event("EpisodeOpen", 51, flow_run_id, app_run_id, {
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })

        try:
            gdp_url = f"https://prod-scoringservice.matific.com/gameDataPersistence?user_data_token={self.user_data_token}&episode_id={episode_id}&assignment_id={assignment_id}&context={context_id}&episode_instance_id={episode_instance_id}"
            await self.client.get(gdp_url, headers=self.headers)
        except Exception:
            pass

        # Episode runtime content loads here in the real client (libs, slate,
        # episode-all$hash, localization, audio packs, fonts, shaders) while
        # the container reports EpisodeLoadingStarted -> EpisodeReady.
        content_task = asyncio.create_task(self._simulate_episode_content_loading(episode_url))

        # Container-side episode lifecycle events (2001/2002/2003), as in the HAR
        grade_code = ud.get("GradeCode") or ud.get("LearningLevel") or "G8"
        container_url = (episode_url + f"&usability=true&language=pt-br&suspendAfterLoad=true&skipEndingScreen=true&grade={grade_code}&platform=WebGLPlayer&screenHeight=745&screenWidth=1020") if "?" in episode_url else episode_url
        await self.send_tracking_event("EpisodeLoadingStarted", 2001, flow_run_id, app_run_id, {
            "activity_context": context_id_int,
            "ec_version": "3.8.5",
            "ep_run_discriminator": flow_run_id,
            "ep_id": episode_id,
            "infra_version": 2.3,
            "invoke_method": "UserClick",
            "instance_id": episode_instance_id,
            "episode_url": container_url,
        })
        await sleep_loading(0.5, 1.2)
        await content_task
        await self.send_tracking_event("EpisodeReady", 2002, flow_run_id, app_run_id, {
            "activity_context": context_id_int,
            "ec_version": "3.8.5",
            "ep_run_discriminator": flow_run_id,
            "ep_id": episode_id,
            "infra_version": 2.3,
            "invoke_method": "UserClick",
            "instance_id": episode_instance_id,
            "episode_url": container_url,
        })
        await self.send_tracking_event("EpisodeRunning", 2003, flow_run_id, app_run_id, {
            "activity_context": context_id_int,
            "ec_version": "3.8.5",
            "ep_run_discriminator": flow_run_id,
            "ep_id": episode_id,
            "infra_version": 2.3,
            "invoke_method": "UserClick",
            "instance_id": episode_instance_id,
            "episode_url": container_url,
        })

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
            "assignment_type": assignment_type_int,
            "assignment_id": assignment_id,
            "is_auto_assigned": 0,
            "episode_instance_id": episode_instance_id,
            "app_version": self.app_version,
            "subject": 0,
            "platform": "WebGLPlayer",
            "is_accessible": False,
            "dev_name": dev_name,
            "problem_count": problem_count,
            "ran_in_adaptive_mode": False,
            "no_progress_bar_in_envelope": False,
            "episode_run_discriminator": episode_run_discriminator,
            "episode_name": episode_name,
            "episode_version": episode_version,
            "since_episode_start_sec": random.randint(30, 70),
            "is_arena": False,
            "path": scoring_path,
            "client_time": int(time.time() * 1000),
            "time_diff": 0,
            "from_tablet": False
        }
        await self.send_scoring_fact(start_fact)
        await self.send_tracking_event("EpisodeInteraction", 2004, flow_run_id, app_run_id, {
            "activity_context": context_id_int,
            "ec_version": "3.8.5",
            "ep_run_discriminator": flow_run_id,
            "ep_id": episode_id,
            "infra_version": 2.3,
            "invoke_method": "UserClick",
            "instance_id": episode_instance_id,
            "episode_url": container_url,
        })

        # Fresh IDs per run: reusing the same problem_id across students or
        # attempts looks like replayed telemetry to the scoring backend.
        problem_ids = [uuid.uuid4().hex for _ in range(problem_count)]

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

        first_try_correct = 0
        last_problem_start = None
        for i in range(problem_count):
            if i > 0 and i % 2 == 0:
                await self.send_ping()
                try:
                    await self.send_keep_alive()
                except Exception:
                    pass
            problem_start_time = time.time()
            update_status(f"Resolvendo quest\u00e3o {i+1} de {problem_count}...", int(10 + (i / problem_count) * 75))

            intro_fact = {
                **start_fact,
                "type": "PresentProblemIntro",
                "problem_index": i,
                "index": i,
                "step": 0,
                "problem_id": problem_ids[i],
                "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
                "client_time": int(time.time() * 1000),
            }
            intro_fact.pop("problem_count", None)
            if last_problem_start is not None:
                intro_fact["since_question_start_sec"] = max(1, int(time.time() - last_problem_start))
            await self.send_scoring_fact(intro_fact)
            await sleep_loading(0.5, 1.2)

            num_mistakes = mistakes_map[i]
            if num_mistakes == 0:
                first_try_correct += 1
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
                        "since_question_start_sec": max(1, int(time.time() - problem_start_time)),
                        "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
                        "client_time": int(time.time() * 1000),
                    }
                    await self.send_scoring_fact(wrong_fact)

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
                "since_question_start_sec": max(1, int(time.time() - problem_start_time)),
                "since_episode_start_sec": int(time.time() * 1000) - episode_start_ms,
                "client_time": int(time.time() * 1000),
            }
            await self.send_scoring_fact(correct_fact)

            last_problem_start = problem_start_time
            if i < problem_count - 1:
                iq_min = float(timings.get("inter_question_min", 0.5))
                iq_max = float(timings.get("inter_question_max", 1.5))
                await asyncio.sleep(random.uniform(iq_min, iq_max))

        update_status("Finalizando tarefa...", 90)
        await sleep_loading(1.0, 2.0)

        score = first_try_correct
        points = score * 20
        now_ms = int(time.time() * 1000)
        finish_fact = {
            **start_fact,
            "type": "FinishEpisode",
            "score": score,
            "points": points,
            "since_episode_start_sec": now_ms - episode_start_ms,
            "since_question_start_sec": max(1, int(time.time() - (last_problem_start or episode_start_ms / 1000))),
            "episode_duration": now_ms - episode_start_ms,
            "client_time": now_ms,
        }
        await self.send_scoring_fact(finish_fact)

        # Post-episode engagement facts (feedback 2 + 206 in one call, as in HAR)
        try:
            eng_base = {
                "episode_slug": slug,
                "episode_run_discriminator": episode_run_discriminator,
                "app_version": self.app_version,
                "platform": "WebGLPlayer",
                "is_offline_fact": False,
                "client_time": int(time.time() * 1000),
            }
            await self.send_scoring_facts([
                {**eng_base, "type": "EpisodeEngagement", "feedback_code": 2},
                {**eng_base, "type": "EpisodeEngagement", "feedback_code": 206},
            ])
        except Exception:
            pass

        await self.send_tracking_event("EpisodeFinished", 2005, flow_run_id, app_run_id, {
            "activity_context": context_id_int,
            "ec_version": "3.8.5",
            "ep_run_discriminator": flow_run_id,
            "ep_id": episode_id,
            "infra_version": 2.3,
            "invoke_method": "UserClick",
            "instance_id": episode_instance_id,
            "episode_url": container_url,
        })
        await self.send_tracking_event("ContainerReportedUserFinished", 55, flow_run_id, app_run_id, {
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })
        await sleep_loading(0.5, 1.0)
        await self.send_tracking_event("screen_view", 16, None, app_run_id, {"screenname": "PostEpisode"})
        await self.send_tracking_event("ScreenViewLoaded", 21, None, app_run_id, {
            "screen_name": "PostEpisode",
            "load_time_in_seconds": round(random.uniform(1.0, 2.5), 3),
        })
        await self.send_tracking_event("EpisodeEngagementGiven", 106, None, app_run_id, {
            "episode_ratings": [2, 206],
            "episode_id": episode_id,
        })
        await self.send_tracking_event("EpisodePostScreenUserAction", 57, flow_run_id, app_run_id, {
            "action": 1,
            "run_uid": flow_run_id,
            "invoke_method": "UserClick",
            "episode": episode_obj,
            "episode_type": "Worksheet",
            "grade": grade_int,
            "topic": episode.get("topic") or "",
            "slug": slug,
            "uuid": student_uuid,
            "episode_url": episode_url,
            "ep_id": episode_id,
            "activity_context": context_id_int,
        })

        try:
            user_state = game_state.get("user_state", [])
            if user_state:
                ranking_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.RankingData"), None)
                currency_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.CurrencyData"), None)
                weekly_goal_row = next((r for r in user_state if r.get("object_type") == "Matific.Mad.UserGoalProgressData" and r.get("item_id") == "weekly_goal"), None)

                post_rows = []
                now_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                if ranking_row:
                    ranking_data = dict(ranking_row.get("data", {}))
                    ranking_data["$type"] = "Matific.Mad.RankingData, AssetsAssembly"
                    ranking_data["currentXp"] = ranking_data.get("currentXp", 0) + 20
                    ranking_data["currentRank"] = (ranking_data["currentXp"] // 100) + 1
                    post_rows.append({
                        "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                        "client_timestamp": now_stamp,
                        "table_name": "user_state",
                        "row_id": ranking_row["row_id"],
                        "data_version_number": 0,
                        "object_type": "Matific.Mad.RankingData",
                        "data": ranking_data,
                        "deprecation_rule": None,
                        "item_id": ranking_row.get("item_id")
                    })
                if weekly_goal_row:
                    weekly_data = dict(weekly_goal_row.get("data", {}))
                    weekly_data["$type"] = "Matific.Mad.UserGoalProgressData, AssetsAssembly"
                    dur_s = int((time.time() * 1000 - episode_start_ms) / 1000)
                    weekly_data["progress"] = weekly_data.get("progress", 0) + dur_s
                    weekly_data["lastProgressDate"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if weekly_data["progress"] >= 1800:
                        weekly_data["isCompleted"] = True
                    post_rows.append({
                        "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                        "client_timestamp": now_stamp,
                        "table_name": "user_state",
                        "row_id": weekly_goal_row["row_id"],
                        "data_version_number": 0,
                        "object_type": "Matific.Mad.UserGoalProgressData",
                        "data": weekly_data,
                        "deprecation_rule": None,
                        "item_id": weekly_goal_row.get("item_id")
                    })
                if currency_row:
                    currency_data = dict(currency_row.get("data", {}))
                    currency_data["$type"] = "Matific.Mad.CurrencyData, AssetsAssembly"
                    currency_data["currentCoins"] = currency_data.get("currentCoins", 0) + (score * 25)
                    post_rows.append({
                        "$type": "Matific.Mad.UserStateRawData, AssetsAssembly",
                        "client_timestamp": now_stamp,
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

        _login_stop.set()
        if _login_task and not _login_task.done():
            _login_task.cancel()
            try:
                await _login_task
            except asyncio.CancelledError:
                pass

        update_status("Conclu\u00eddo com sucesso!", 100)
        logger.info(f"[MATIFIC-PLAY] Episode {slug} completed. Score={score}/{problem_count}")
        return True
