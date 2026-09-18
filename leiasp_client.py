import asyncio
import base64
import datetime
import hashlib
import io
import json
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from typing import Optional, Tuple, Dict, Any, List

import httpx
from client import RoutingAsyncClient, _get_browser_context

logger = logging.getLogger("saladopassado.leiasp")

class LeiaSPAuthError(Exception):
    pass

class LeiaSPClient:
    SED_INTEGRATION_URL = "https://sedintegracoes.educacao.sp.gov.br/saladofuturobffapi/integracoes/Token?plataforma=LeiaSP%2B"
    SED_APIM_KEY = "d701a2043aa24d7ebb37e9adf60d043b"
    ELEFANTE_OAUTH_BASE = "https://prod-apiaccounts.elefanteletrado.com.br/api/oauth/seducsp/token"
    ELEFANTE_STUDENT_API = "https://prod-apistudent.elefanteletrado.com.br"
    ELEFANTE_CDN_BASE = "https://prod-us.elefanteletrado.com.br/cdn"

    def __init__(self, token_sed: Optional[str] = None, leiasp_jwt: Optional[str] = None, fp: Optional[dict] = None):
        self.token_sed = token_sed
        self.leiasp_jwt = leiasp_jwt
        self.fp = fp or _get_browser_context()
        self.client = RoutingAsyncClient(timeout=30.0)
        self.elefante_token: Optional[str] = None
        self.headers_elefante: Dict[str, str] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def authenticate(self, token_sed: Optional[str] = None, leiasp_jwt: Optional[str] = None) -> str:
        if leiasp_jwt:
            self.leiasp_jwt = leiasp_jwt
        if token_sed:
            self.token_sed = token_sed

        if not self.leiasp_jwt:
            if not self.token_sed:
                raise LeiaSPAuthError("Token SED ou leiasp_jwt não fornecido.")

            headers_sed = {
                "User-Agent": self.fp["user-agent"],
                "sec-ch-ua": self.fp["sec-ch-ua"],
                "sec-ch-ua-mobile": self.fp["sec-ch-ua-mobile"],
                "sec-ch-ua-platform": self.fp["sec-ch-ua-platform"],
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "pt-BR,pt;q=0.9",
                "X-Product-Name": "SalaDoFuturo",
                "Ocp-Apim-Subscription-Key": self.SED_APIM_KEY,
                "Authorization": f"Bearer {self.token_sed}",
            }

            resp_tok = await self.client.get(self.SED_INTEGRATION_URL, headers=headers_sed)
            if resp_tok.status_code != 200:
                raise LeiaSPAuthError(f"Falha ao obter token SED LeiaSP+: HTTP {resp_tok.status_code} - {resp_tok.text[:200]}")

            try:
                self.leiasp_jwt = resp_tok.json().get("data")
            except Exception as e:
                raise LeiaSPAuthError(f"Resposta inválida da API SED LeiaSP+: {e}")

        if not self.leiasp_jwt:
            raise LeiaSPAuthError("API SED não retornou campo 'data' com o JWT do LeiaSP.")

        oauth_url = f"{self.ELEFANTE_OAUTH_BASE}?token={self.leiasp_jwt}"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as oauth_client:
            resp_oauth = await oauth_client.get(
                oauth_url,
                headers={"User-Agent": self.fp["user-agent"], "Accept-Language": "pt-BR,pt;q=0.9"},
            )

        elefante_token = None
        if resp_oauth.status_code in (301, 302, 307, 308):
            loc = resp_oauth.headers.get("location") or resp_oauth.headers.get("Location")
            if loc:
                t_param = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get("t", [None])[0]
                if t_param:
                    try:
                        elefante_token = json.loads(base64.b64decode(t_param).decode("utf-8")).get("access_token")
                    except Exception as dec_err:
                        logger.warning(f"[LeiaSP] Falha ao decodificar token OAuth: {dec_err}")

        if not elefante_token and resp_oauth.status_code == 200:
            try:
                data = resp_oauth.json()
                elefante_token = data.get("access_token") or data.get("token")
            except Exception:
                pass

        if not elefante_token:
            raise LeiaSPAuthError("Não foi possível extrair o access_token na resposta OAuth do Elefante Letrado.")

        self.elefante_token = elefante_token
        self.headers_elefante = {
            "Authorization": f"Bearer {self.elefante_token}",
            "User-Agent": self.fp["user-agent"],
            "sec-ch-ua": self.fp["sec-ch-ua"],
            "sec-ch-ua-mobile": self.fp["sec-ch-ua-mobile"],
            "sec-ch-ua-platform": self.fp["sec-ch-ua-platform"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "origin": "https://reader.elefanteletrado.com.br",
            "referer": "https://reader.elefanteletrado.com.br/",
        }
        return self.elefante_token

    async def get_library_books(self) -> List[Dict[str, Any]]:
        if not self.elefante_token:
            await self.authenticate()

        discover_books, readings_books = [], []
        try:
            r = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/library/discover/", headers=self.headers_elefante)
            if r.status_code == 200:
                discover_books = r.json() or []
        except Exception as e:
            logger.warning(f"[LeiaSP] Falha ao buscar /discover: {e}")

        try:
            r = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/library/book/readings", headers=self.headers_elefante)
            if r.status_code == 200:
                readings_books = r.json() or []
        except Exception as e:
            logger.warning(f"[LeiaSP] Falha ao buscar /readings: {e}")

        merged: Dict[int, Dict[str, Any]] = {}
        for b in discover_books:
            bid = b.get("Id") or b.get("BookId")
            if bid:
                merged[bid] = dict(b)

        for b in readings_books:
            bid = b.get("Id") or b.get("BookId")
            if not bid:
                continue
            if bid in merged:
                for k, v in b.items():
                    if v is not None and v != "" and v != 0:
                        merged[bid][k] = v
                if "IsReadCompleted" in b:
                    merged[bid]["IsReadCompleted"] = b["IsReadCompleted"]
                if "IsQuizCompleted" in b:
                    merged[bid]["IsQuizCompleted"] = b["IsQuizCompleted"]
            else:
                merged[bid] = dict(b)

        results = []
        for b in merged.values():
            num_pages = b.get("NumberPages") or 0
            page = b.get("Page") or 0
            raw_percent = b.get("ReadingPercent")
            if raw_percent is not None and raw_percent > 0:
                progress = float(raw_percent)
            elif num_pages > 0 and page > 0:
                progress = round((page / num_pages) * 100, 1)
            else:
                progress = 0.0

            is_complete = bool(b.get("IsReadCompleted") or (progress >= 100.0))

            epub_path = b.get("EpubUrl") or b.get("UrlToEpubFile") or b.get("FullUrlToEpubFile") or b.get("EpubFilePath") or ""
            epub_full = f"{self.ELEFANTE_CDN_BASE}{epub_path}" if (epub_path and epub_path.startswith("/")) else epub_path

            cover_path = b.get("CoverPageUrl") or b.get("ThumbnailCoverPic") or b.get("CoverUrl") or b.get("CoverThumbnailUrl") or b.get("UrlToCoverImage") or ""
            if cover_path and cover_path.startswith("/"):
                cover_path = f"{self.ELEFANTE_CDN_BASE}{cover_path}"

            authors_val = b.get("Authors")
            author_str = ", ".join(authors_val) if isinstance(authors_val, list) and authors_val else (b.get("AuthorStr") or b.get("Author") or "Desconhecido")
            level_str = b.get("LevelName") or b.get("Level") or b.get("Genre") or "Leitura"

            results.append({
                "id": b.get("Id") or b.get("BookId"),
                "title": b.get("BookTitle") or b.get("Title") or "Sem Título",
                "author": author_str,
                "publisher": b.get("Publisher") or "",
                "total_pages": num_pages,
                "current_page": page,
                "progress": progress,
                "is_complete": is_complete,
                "is_quiz_active": bool(b.get("IsQuizActive")),
                "quiz_triggered_at": b.get("QuizTriggeredAt") or 1,
                "cover_url": cover_path,
                "epub_url": epub_full,
                "level": level_str,
                "genre": b.get("Genre") or "",
                "synopsis": b.get("Synopsis") or b.get("Description") or "",
            })

        results.sort(key=lambda x: (x["is_complete"], -x["progress"], x["title"]))
        return results

    async def get_book_metadata(self, book_id: int) -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()
        resp = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/student/books/{book_id}", headers=self.headers_elefante)
        if resp.status_code != 200:
            raise Exception(f"Falha ao obter metadados do livro {book_id}: HTTP {resp.status_code}")
        return resp.json()

    async def parse_epub(self, epub_url: str, total_pages: int) -> Tuple[str, List[str]]:
        if not epub_url:
            return "", []

        try:
            resp = await self.client.get(epub_url, headers=self.headers_elefante, timeout=60.0)
            if resp.status_code not in (200, 206):
                return "", []
            epub_bytes = io.BytesIO(resp.content)
        except Exception as e:
            logger.warning(f"[LeiaSP] Falha no download do EPUB {epub_url}: {e}")
            return "", []

        try:
            with zipfile.ZipFile(epub_bytes, "r") as z:
                try:
                    container = z.read("META-INF/container.xml").decode("utf-8", errors="ignore")
                except KeyError:
                    return "", []

                match = re.search(r'full-path=["\']([^"\']+)["\']', container)
                opf_path = match.group(1) if match else "OEBPS/content.opf"
                epub_hash = hashlib.sha1(f"com.colibrio.zipstream:///com.colibrio.zipstream:///{opf_path}".encode("utf-8")).hexdigest()

                try:
                    opf = z.read(opf_path).decode("utf-8", errors="ignore")
                except KeyError:
                    return epub_hash, []

                root = ET.fromstring(opf)
                ns = {"opf": "http://www.idpf.org/2007/opf"}
                spine = root.find("opf:spine", ns)
                manifest = root.find("opf:manifest", ns)
                if spine is None or manifest is None:
                    return epub_hash, []

                id_to_href = {item.get("id"): item.get("href") for item in manifest.findall("opf:item", ns)}
                opf_dir = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
                spine_items = []
                total_size = 0

                for idx, itemref in enumerate(spine.findall("opf:itemref", ns)):
                    href = id_to_href.get(itemref.get("idref"))
                    if not href:
                        continue
                    file_path = f"{opf_dir}/{href}" if opf_dir else href
                    try:
                        size = z.getinfo(file_path).file_size
                    except KeyError:
                        size = 0

                    element_id = None
                    try:
                        html = z.read(file_path).decode("utf-8", errors="ignore")
                        id_match = re.search(r'<(\w+)[^>]*id=["\']([^"\']+)["\']', html, re.IGNORECASE)
                        if id_match:
                            element_id = id_match.group(2)
                    except Exception:
                        pass

                    spine_items.append({
                        "index": idx,
                        "size": size,
                        "element_id": element_id or f"item-{idx}",
                    })
                    total_size += size

                if not spine_items or total_size == 0:
                    return epub_hash, []

                cfi_map = []
                for p in range(1, total_pages + 1):
                    target_byte = ((p - 0.5) / max(total_pages, 1)) * total_size
                    accum = 0
                    chosen = spine_items[0]
                    for itm in spine_items:
                        accum += itm["size"]
                        if accum >= target_byte:
                            chosen = itm
                            break

                    spine_idx = chosen["index"]
                    elem_id = chosen["element_id"]
                    cfi_map.append(f"com.colibrio.epub.signature:{epub_hash}#epubcfi(/6/{(spine_idx + 1) * 2}!/4[{elem_id}]/1:0)")

                return epub_hash, cfi_map

        except Exception as e:
            logger.warning(f"[LeiaSP] Erro ao parsear EPUB: {e}")
            return "", []

    async def simulate_colibrio_epub_load(self, epub_url: str, job: Optional[dict] = None) -> bool:
        try:
            head_resp = await self.client.head(epub_url, headers=self.headers_elefante, timeout=30.0)
            if head_resp.status_code not in (200, 204):
                return False

            content_length = int(head_resp.headers.get("Content-Length", 0))
            if not content_length:
                return False

            tail_size = min(65536, content_length)
            tail_start = content_length - tail_size
            tail_resp = await self.client.get(
                epub_url,
                headers={**self.headers_elefante, "Range": f"bytes={tail_start}-{content_length - 1}"},
                timeout=30.0,
            )
            if tail_resp.status_code not in (200, 206):
                return False

            tail_bytes = tail_resp.content
            eocd_pos = tail_bytes.rfind(b"\x50\x4b\x05\x06")
            if eocd_pos == -1:
                return False

            cd_size = int.from_bytes(tail_bytes[eocd_pos + 12 : eocd_pos + 16], "little")
            cd_offset = int.from_bytes(tail_bytes[eocd_pos + 16 : eocd_pos + 20], "little")
            cd_end = cd_offset + cd_size

            if cd_offset >= tail_start and cd_end <= content_length:
                cd_bytes = tail_bytes[cd_offset - tail_start : cd_offset - tail_start + cd_size]
            else:
                cd_resp = await self.client.get(
                    epub_url,
                    headers={**self.headers_elefante, "Range": f"bytes={cd_offset}-{cd_end - 1}"},
                    timeout=30.0,
                )
                cd_bytes = cd_resp.content if cd_resp.status_code in (200, 206) else b""

            if not cd_bytes:
                return False

            files, pos = [], 0
            while pos < len(cd_bytes):
                if cd_bytes[pos : pos + 4] != b"\x50\x4b\x01\x02":
                    break
                comp_size = int.from_bytes(cd_bytes[pos + 20 : pos + 24], "little")
                fn_len = int.from_bytes(cd_bytes[pos + 28 : pos + 30], "little")
                extra_len = int.from_bytes(cd_bytes[pos + 30 : pos + 32], "little")
                comment_len = int.from_bytes(cd_bytes[pos + 32 : pos + 34], "little")
                header_offset = int.from_bytes(cd_bytes[pos + 42 : pos + 46], "little")
                pos += 46 + fn_len + extra_len + comment_len
                files.append((header_offset, comp_size))

            if not files:
                return False

            files.sort(key=lambda x: x[0])
            spans = [(off, files[i + 1][0] if i + 1 < len(files) else content_length) for i, (off, _) in enumerate(files)]

            blocks = []
            cur_start, cur_end = spans[0]
            for off, end in spans[1:]:
                size = end - off
                if size >= 100_000:
                    blocks.append((cur_start, cur_end))
                    f_start, f_end = off, end
                    while f_end - f_start > 1_000_000:
                        blocks.append((f_start, f_start + 1_000_000))
                        f_start += 1_000_000
                    blocks.append((f_start, f_end))
                    cur_start, cur_end = None, None
                elif cur_start is not None and (cur_end - cur_start + size) <= 100_000:
                    cur_end = end
                else:
                    if cur_start is not None:
                        blocks.append((cur_start, cur_end))
                    cur_start, cur_end = off, end

            if cur_start is not None:
                blocks.append((cur_start, cur_end))

            final_ranges = [(s, e - 1) for s, e in blocks]
            tail_ranges = [r for r in final_ranges if r[1] >= content_length - 1024]
            ordered_ranges = tail_ranges + [r for r in final_ranges if r not in tail_ranges]

            if job:
                job.setdefault("logs", []).append(f"Carregamento Colibrio: disparando {len(ordered_ranges)} range requests para o EPUB...")

            for r_start, r_end in ordered_ranges:
                await self.client.get(epub_url, headers={**self.headers_elefante, "Range": f"bytes={r_start}-{r_end}"}, timeout=30.0)

            return True
        except Exception as e:
            logger.warning(f"[LeiaSP] Simulação Colibrio falhou: {e}")
            return False

    async def start_session(self, book_id: int):
        if not self.elefante_token:
            await self.authenticate()
        try:
            await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/highlights/get-highlights/{book_id}", headers=self.headers_elefante, timeout=15.0)
            await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/bookmarks/get-bookmarks/{book_id}", headers=self.headers_elefante, timeout=15.0)
        except Exception:
            pass

    async def send_page_progress(self, book_id: int, page: int, total_pages: int, cfi_value: str, time_spent: int, is_complete: bool = False, read_type: str = "Read") -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()

        is_done = is_complete or (page >= total_pages)
        payload = {
            "CFI": cfi_value,
            "BookId": str(book_id),
            "TimeElapsed": int(time_spent),
            "ReadType": read_type,
            "Page": int(page),
            "IsComplete": is_done,
            "ReadDate": datetime.date.today().strftime("%d/%m/%Y"),
            "PageCount": int(total_pages),
            "TimezoneOffset": 180,
        }

        url_em = f"{self.ELEFANTE_STUDENT_API}/v1/student/books/{book_id}/progress_em/{read_type}"
        headers = {**self.headers_elefante, "Content-Type": "application/json; charset=UTF-8"}

        try:
            resp = await self.client.post(url_em, json=payload, headers=headers, timeout=30.0)
            if resp.status_code == 401:
                await self.authenticate()
                headers = {**self.headers_elefante, "Content-Type": "application/json; charset=UTF-8"}
                resp = await self.client.post(url_em, json=payload, headers=headers, timeout=30.0)

            if resp.status_code in (404, 405):
                url_fallback = f"{self.ELEFANTE_STUDENT_API}/v1/student/books/{book_id}/progressbybody/{read_type}"
                resp = await self.client.post(url_fallback, json=payload, headers=headers, timeout=30.0)

            if resp.status_code == 200:
                try:
                    data = resp.json() or {}
                except Exception:
                    data = {}
                return {
                    "success": True,
                    "is_completed": data.get("IsCompletedWithSuccess", False),
                    "reward": data.get("Reward", 0),
                    "total_time": data.get("TotalTimeSpend", 0.0),
                    "min_time": data.get("CloseBookEventInfo", {}).get("MinimumTime", 0),
                    "data": data,
                }
            return {"success": False, "is_completed": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"success": False, "is_completed": False, "error": str(e)}

    async def close_book_checkpoint(self, book_id: int, time_spent: int = 0, read_type: str = "Read") -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()

        type_flag = "1" if read_type == "Listen" else "0"
        url = f"{self.ELEFANTE_STUDENT_API}/v1/book-reading/close-book/{book_id}/{type_flag}?currentPageTime={int(time_spent)}"
        try:
            resp = await self.client.post(url, headers=self.headers_elefante, timeout=30.0)
            if resp.status_code == 401:
                await self.authenticate()
                resp = await self.client.post(url, headers=self.headers_elefante, timeout=30.0)
            if resp.status_code == 200:
                try:
                    return resp.json() or {}
                except Exception:
                    return {"success": True}
            return {"success": False, "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_student_stats(self) -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()
        try:
            resp = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/student/stats", headers=self.headers_elefante, timeout=30.0)
            if resp.status_code == 401:
                await self.authenticate()
                resp = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v1/student/stats", headers=self.headers_elefante, timeout=30.0)
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}

    async def finish_book(self, book_id: int, total_pages: int, cfi_value: str, time_spent: int, read_type: str = "Read") -> Dict[str, Any]:
        progress_res = await self.send_page_progress(book_id, total_pages, total_pages, cfi_value, time_spent, is_complete=True, read_type=read_type)
        stats = await self.get_student_stats()
        close_res = await self.close_book_checkpoint(book_id, time_spent=0, read_type=read_type)
        return {
            "progress": progress_res,
            "stats": stats,
            "close": close_res,
            "is_completed_with_success": progress_res.get("is_completed", False),
            "points": stats.get("Points", progress_res.get("reward", 0)),
        }

    async def fetch_quiz(self, book_id: int) -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()
        try:
            resp = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v2/student/books/{book_id}/quiz", headers=self.headers_elefante, timeout=30.0)
            if resp.status_code == 401:
                await self.authenticate()
                resp = await self.client.get(f"{self.ELEFANTE_STUDENT_API}/v2/student/books/{book_id}/quiz", headers=self.headers_elefante, timeout=30.0)
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}

    async def evaluate_dissertative_answer(self, book_id: int, question_id: int, question_text: str, answer_text: str) -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()
        payload = {
            "QuestionId": int(question_id),
            "BookId": int(book_id),
            "Question": question_text,
            "Answer": answer_text,
            "Dimensions": [],
            "Workspace": "",
        }
        try:
            resp = await self.client.post(
                f"{self.ELEFANTE_STUDENT_API}/v1/ai/dissertative-answer-evaluation/V2",
                json=payload,
                headers=self.headers_elefante,
                timeout=30.0,
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}

    async def submit_milestone_quiz(self, book_id: int, milestone: Any, questions_payload: list) -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()
        payload = {
            "Questions": questions_payload,
            "CurrentMilestone": milestone,
        }
        try:
            resp = await self.client.post(
                f"{self.ELEFANTE_STUDENT_API}/v2/student/books/{book_id}/quiz",
                json=payload,
                headers=self.headers_elefante,
                timeout=30.0,
            )
            return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def finish_quiz(self, book_id: int) -> Dict[str, Any]:
        if not self.elefante_token:
            await self.authenticate()
        try:
            resp = await self.client.post(
                f"{self.ELEFANTE_STUDENT_API}/v2/student/books/{book_id}/finish-quiz",
                json={},
                headers=self.headers_elefante,
                timeout=30.0,
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}
