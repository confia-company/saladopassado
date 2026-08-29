import base64
import json
import logging
import re
import unicodedata
from typing import Optional, Tuple
import httpx

import config
from config import (
    AI_BASE_URL,
    AI_API_KEY,
    TASK_PROMPT_TEMPLATE,
    ESSAY_PROMPT_TEMPLATE,
    ESSAY_HUMANIZE_INSTRUCTIONS,
    TEXT_AI_HUMANIZE_INSTRUCTIONS,
)
from database import (
    resolve_cached_answers,
    save_ai_cached_answers,
    save_question_level_ai_answers,
    db_call,
)

logger = logging.getLogger("saladopassado.ai")

def _strip_html(html_str: str) -> str:
    if not html_str:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html_str)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    return re.sub(r'\s+', ' ', text).strip()

def _extract_images_from_task(task_data: dict) -> list[str]:
    """Collect image URLs referenced in question statements or media fields (ignoring decorative banners)."""
    images = []
    for q in task_data.get("questions", []):
        if q.get("type") in ("info", "section"):
            continue
        statement = q.get("statement", "")
        img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', statement)
        for m in img_matches:
            if m not in images and "icon" not in m.lower() and "badge" not in m.lower():
                images.append(m)
        
        if q.get("media_type") == "image" and q.get("media_url"):
            u = q.get("media_url")
            if u not in images:
                images.append(u)

        options = q.get("options")
        if isinstance(options, dict):
            for opt_val in options.values():
                if isinstance(opt_val, dict):
                    opt_stmt = opt_val.get("statement", "")
                    for m in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', opt_stmt):
                        if m not in images:
                            images.append(m)
                    if opt_val.get("media_type") == "image" and opt_val.get("media_url"):
                        u = opt_val.get("media_url")
                        if u not in images:
                            images.append(u)
    return images

async def _download_media_as_base64(url: str) -> Tuple[str, str]:
    """Download image or audio URL and return (base64_data, mime_type)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise Exception(f"Failed to download media {url}: HTTP {resp.status_code}")
        mime = resp.headers.get("content-type", "image/png").split(";")[0].strip()
        data_b64 = base64.b64encode(resp.content).decode("utf-8")
        return data_b64, mime

def _build_essay_ai_prompt(task_data: dict) -> str:
    """Build prompt for essay (Redação) tasks."""
    title = task_data.get("title", "")
    desc = task_data.get("description", "")
    questions = task_data.get("questions", [])
    essay_q = next((q for q in questions if q.get("type") == "essay"), None)
    if not essay_q:
        return ""

    options = essay_q.get("options") or {}
    genre = options.get("genre", {})
    genre_statement = genre.get("statement", "")
    min_words = genre.get("min_word") or options.get("min_word_count") or 800
    max_words = genre.get("max_word") or options.get("max_word_count") or 1600
    text_count_unit = options.get("text_count_unit", "char")

    assessed_skills = options.get("assessed_skills", [])
    skills_text = ""
    for s in assessed_skills:
        skills_text += f"\n- {s.get('statement', '')}:\n{s.get('description', '')}\n"

    support_text = _strip_html(options.get("support_text", ""))
    support_text = support_text.replace("[...]", "").replace("...", ". ").replace("…", ". ")

    prompt = ESSAY_PROMPT_TEMPLATE
    prompt = prompt.replace("{{TITLE}}", str(title))
    prompt = prompt.replace("{{GENRE_STATEMENT}}", str(genre_statement))
    prompt = prompt.replace("{{DESCRIPTION}}", str(desc))
    prompt = prompt.replace("{{MIN_WORDS}}", str(min_words))
    prompt = prompt.replace("{{MAX_WORDS}}", str(max_words))
    prompt = prompt.replace("{{TEXT_COUNT_UNIT}}", str(text_count_unit))
    prompt = prompt.replace("{{SUPPORT_TEXT}}", str(support_text))
    prompt = prompt.replace("{{SKILLS_TEXT}}", str(skills_text))
    prompt = prompt.replace("{{HUMANIZE_INSTRUCTIONS}}", ESSAY_HUMANIZE_INSTRUCTIONS)
    return prompt

def _build_ai_prompt(task_data: dict) -> str:
    """Build prompt for standard objective / dissertative tasks."""
    if task_data.get("is_essay") or task_data.get("task_is_essay") or any(q.get("type") == "essay" for q in task_data.get("questions", [])):
        return _build_essay_ai_prompt(task_data)

    title = task_data.get("title", "")
    desc = task_data.get("description", "")
    questions = task_data.get("questions", [])

    questions_section = ""
    for q in questions:
        q_type = q.get("type", "")
        q_id = q.get("id", "")
        statement = _strip_html(q.get("statement", ""))
        statement = statement.replace("[...]", "").replace("...", ". ").replace("…", ". ")

        if q_type in ("info", "section"):
            if statement:
                questions_section += f"\n[CONTEXTO] {statement[:300]}\n"
            continue

        questions_section += f"\n--- QUESTÃO {q_id} (tipo: {q_type}) ---\n"
        questions_section += f"Enunciado: {statement}\n"

        options = q.get("options") or {}

        if q_type in ("single", "multi", "true-false") and isinstance(options, dict):
            for k, opt in options.items():
                if isinstance(opt, dict):
                    questions_section += f"  {k}) {_strip_html(opt.get('statement', ''))}\n"
                else:
                    questions_section += f"  {k}) {_strip_html(str(opt))}\n"

        elif q_type == "fill-words" and isinstance(options, dict):
            phrase_parts = options.get("phrase", [])
            txt, blanks = "", 0
            for p in phrase_parts:
                if p.get("type") == "text":
                    txt += p.get("value", "")
                elif p.get("type") == "select":
                    blanks += 1
                    txt += f" [LACUNA_{blanks}] "
            questions_section += f"Frase com lacunas: {txt}\n"
            questions_section += f"Opções de palavras para preencher: {', '.join(options.get('items', []))}\n"

        elif q_type == "cloud" and isinstance(options, dict):
            words = options.get("words", [])
            questions_section += f"Palavras disponíveis para ordenar: {', '.join(words)}\n"

        elif q_type == "text_ai" and isinstance(options, dict):
            kw = options.get("ai_grading_keywords", [])
            if kw:
                questions_section += f"Palavras-chave obrigatórias a incluir: {', '.join(kw)}\n"
            questions_section += f"Min/Max caracteres: {options.get('min_text_count', 1)}/{options.get('max_text_count', 2000)}\n"
            questions_section += TEXT_AI_HUMANIZE_INSTRUCTIONS + "\n"

        elif q_type == "fill-letters" and isinstance(options, dict):
            questions_section += f"Número de letras: {options.get('letters', 0)}\n"

        elif q_type == "order-sentences" and isinstance(options, dict):
            incorrects = options.get("incorrects", [])
            sentences = options.get("sentences", [])
            if incorrects:
                for s in incorrects:
                    questions_section += f"  - {s.get('value','')}\n"
            elif sentences:
                for s in sentences:
                    questions_section += f"  - {s}\n"
            questions_section += "Instrução: Retorne a lista ordenada contendo o texto exato das sentenças.\n"

    prompt = TASK_PROMPT_TEMPLATE
    prompt = prompt.replace("{{TITLE}}", str(title))
    prompt = prompt.replace("{{DESCRIPTION}}", str(desc))
    prompt = prompt.replace("{{QUESTIONS_SECTION}}", str(questions_section))
    return prompt

async def _call_ai_completion(
    prompt: str,
    images: list[str] = None,
    system_instruction: str = None,
    model: str = None,
    timeout: float = 35.0
) -> Tuple[str, str]:
    """Call OpenAI-compatible chat completion endpoint with automatic fallback across candidate models."""
    url = f"{AI_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    if images:
        content = [{"type": "text", "text": prompt}]
        for img_url in images:
            try:
                b64, mime = await _download_media_as_base64(img_url)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
            except Exception as e:
                logger.warning(f"Could not download image {img_url}: {e}")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
    else:
        content = prompt

    if system_instruction is None:
        system_instruction = "Você é um assistente educacional brasileiro de elite. Responda TODAS as questões fornecidas estritamente no formato solicitado."

    candidate_models = []
    if model:
        candidate_models.append(model)
    for m in getattr(config, "CANDIDATE_MODELS", ["ds-web/deepseek-v4-flash-think", "gemini-web/gemini-3.6-flash", "claude-web/claude-5-sonnet"]):
        if m and m not in candidate_models:
            candidate_models.append(m)

    last_error = None
    for chosen_model in candidate_models:
        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": content}
            ],
            "temperature": 0.2,
            "stream": True
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    last_error = Exception(f"AI API HTTP {resp.status_code}: {resp.text[:200]}")
                    continue

                text = resp.text.strip()
                if text.startswith("data:"):
                    chunks = []
                    for line in text.splitlines():
                        line = line.strip()
                        if line.startswith("data:") and not line.endswith("[DONE]"):
                            json_part = line[len("data:"):].strip()
                            try:
                                chunk_obj = json.loads(json_part)
                                delta = chunk_obj.get("choices", [{}])[0].get("delta", {})
                                if delta.get("content"):
                                    chunks.append(delta["content"])
                            except Exception:
                                pass
                    full_res = "".join(chunks)
                    if full_res.strip():
                        return full_res, chosen_model

                data = resp.json()
                if "error" in data:
                    last_error = Exception(f"AI API error: {data['error']}")
                    continue
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    res = msg.get("content")
                    if res:
                        return str(res), chosen_model

        except Exception as e:
            last_error = e
            continue

    if last_error:
        raise last_error
    raise Exception("All candidate AI models failed to return content")

_call_omniroute_ai = _call_ai_completion

def _parse_ai_json(text: str) -> Optional[dict]:
    """Parse JSON out of AI response using markdown block, bracket slice, or array slice."""
    if not text:
        return None
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace+1])
        except Exception:
            pass

    first_bracket = text.find('[')
    last_bracket = text.rfind(']')
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(text[first_bracket:last_bracket+1])
        except Exception:
            pass

    return None

def _parse_essay_raw(text: str, questions: list) -> dict:
    """Parse essay response into {str(qid): {question_id, question_type: 'essay', answer: {title, body}}}."""
    essay_q = next((q for q in questions if q.get("type") == "essay"), None)
    if not essay_q:
        return {}
    qid = essay_q.get("id")

    title = ""
    body = ""
    raw_str = str(text or "").strip()

    parsed_json = _parse_ai_json(raw_str)
    if parsed_json and isinstance(parsed_json, dict):
        if str(qid) in parsed_json and isinstance(parsed_json[str(qid)], dict):
            entry = parsed_json[str(qid)]
            ans = entry.get("answer") if "answer" in entry else entry
            if isinstance(ans, dict):
                title = ans.get("title") or ans.get("titulo") or ""
                body = ans.get("body") or ans.get("redacao") or ans.get("texto") or ans.get("text") or ""
        elif "title" in parsed_json or "titulo" in parsed_json:
            title = parsed_json.get("title") or parsed_json.get("titulo") or ""
            body = parsed_json.get("body") or parsed_json.get("redacao") or parsed_json.get("texto") or parsed_json.get("text") or ""

    if not body and raw_str:
        clean_text = raw_str
        clean_text = re.sub(r'^```[\w]*\n?', '', clean_text)
        clean_text = re.sub(r'\n?```$', '', clean_text).strip()
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        if lines:
            title = lines[0]
            title = re.sub(r'^(?:título|titulo|title|#+)\s*[:\-]?\s*', '', title, flags=re.IGNORECASE).strip('"\'' )
            body = "\n\n".join(lines[1:])

    return {
        str(qid): {
            "question_id": qid,
            "question_type": "essay",
            "answer": {
                "title": title or "Redação de Nota Máxima",
                "body": body or raw_str
            }
        }
    }

def _convert_parsed_structure_to_qid_map(parsed: any, task_data: dict) -> dict:
    """Convert any AI output format (dict, list, indexed keys) to {str(qid): raw_answer}."""
    questions = task_data.get("questions", [])
    answerable = [q for q in questions if q.get("type") not in ("info", "section")]
    qid_map = {}

    if isinstance(parsed, list):
        for idx, item in enumerate(parsed):
            if isinstance(item, dict):
                qid = item.get("question_id") or item.get("id")
                if not qid and idx < len(answerable):
                    qid = answerable[idx].get("id")
                if qid:
                    qid_map[str(qid)] = item
            elif idx < len(answerable):
                qid = answerable[idx].get("id")
                qid_map[str(qid)] = item

    elif isinstance(parsed, dict):
        for k, v in parsed.items():
            k_str = str(k).strip()
            if any(str(q.get("id")) == k_str for q in answerable):
                qid_map[k_str] = v
                continue

            m = re.search(r'\d+', k_str)
            if m:
                idx = int(m.group(0))
                if 1 <= idx <= len(answerable):
                    target_qid = str(answerable[idx - 1].get("id"))
                    qid_map[target_qid] = v
                elif 0 <= idx < len(answerable):
                    target_qid = str(answerable[idx].get("id"))
                    qid_map[target_qid] = v
                else:
                    qid_map[k_str] = v
            else:
                qid_map[k_str] = v

    return qid_map

def _normalize_ai_answers(raw_parsed: any, task_data: dict) -> dict:
    """Ensure all answers match IP.TV expected formats and types."""
    if not raw_parsed or not task_data:
        return {}

    qid_map = _convert_parsed_structure_to_qid_map(raw_parsed, task_data)
    normalized = {}
    questions = task_data.get("questions", [])

    for q in questions:
        q_id = q.get("id")
        q_type = q.get("type")
        if not q_id or q_type in ("info", "section"):
            continue

        entry = qid_map.get(str(q_id))
        if entry is None:
            continue

        safe_qid = int(q_id) if str(q_id).isdigit() else q_id

        if isinstance(entry, dict):
            if "answer" in entry:
                ans_val = entry["answer"]
            elif "resposta" in entry:
                ans_val = entry["resposta"]
            elif "palavras" in entry:
                ans_val = entry["palavras"]
            else:
                ans_val = entry
        else:
            ans_val = entry

        if q_type == "fill-letters":
            options = q.get("options") or {}
            expected_len = options.get("letters", 0) if isinstance(options, dict) else 0
            if isinstance(ans_val, list):
                ans_str = "".join(str(x) for x in ans_val)
            elif isinstance(ans_val, dict):
                ans_str = str(ans_val.get("0") or next(iter(ans_val.values()), ""))
            else:
                ans_str = str(ans_val or "")

            if expected_len > 0:
                if len(ans_str) > expected_len:
                    ans_str = ans_str[:expected_len]
                elif len(ans_str) < expected_len:
                    ans_str = ans_str.ljust(expected_len, "")

            corr = {
                "preterito": "pretérito", "gerundio": "gerúndio", "participio": "particípio",
                "oxitona": "oxítona", "paroxitona": "paroxítona", "proparoxitona": "proparoxítona",
                "digrafo": "dígrafo", "adverbio": "advérbio", "preposicao": "preposição",
                "conjuncao": "conjunção", "interjeicao": "interjeição", "concordancia": "concordância",
                "acentuacao": "acentuação", "pontuacao": "pontuação", "metafora": "metáfora",
            }
            nfkd = "".join(c for c in unicodedata.normalize("NFD", ans_str.lower()) if unicodedata.category(c) != "Mn")
            if nfkd in corr:
                ans_str = corr[nfkd]
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": ans_str}

        elif q_type == "cloud":
            options = q.get("options") or {}
            avail = options.get("words", []) if isinstance(options, dict) else []
            if avail:
                if isinstance(ans_val, str):
                    ai_words = ans_val.split()
                elif isinstance(ans_val, list):
                    ai_words = [str(w) for w in ans_val]
                else:
                    ai_words = avail

                matched = []
                avail_counts = {w: avail.count(w) for w in avail}
                for w in ai_words:
                    clean_w = re.sub(r'[^a-zA-Z0-9]', '', unicodedata.normalize('NFD', w).lower())
                    best_match = None
                    for orig in avail:
                        if avail_counts.get(orig, 0) <= 0:
                            continue
                        clean_orig = re.sub(r'[^a-zA-Z0-9]', '', unicodedata.normalize('NFD', orig).lower())
                        if clean_orig == clean_w:
                            best_match = orig
                            break
                    if best_match:
                        matched.append(best_match)
                        avail_counts[best_match] -= 1

                normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": matched if matched else avail}

        elif q_type == "fill-words":
            options = q.get("options") or {}
            available_items = options.get("items", []) if isinstance(options, dict) else []
            if isinstance(ans_val, list):
                clean_list = [str(x).strip() for x in ans_val]
            elif isinstance(ans_val, str):
                clean_list = [x.strip() for x in ans_val.split(",") if x.strip()]
            else:
                clean_list = available_items
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": clean_list}

        elif q_type == "single":
            options = q.get("options") or {}
            real_keys = list(options.keys()) if isinstance(options, dict) else ["0", "1", "2", "3"]
            letter_map = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
            
            selected_idx = None
            if isinstance(ans_val, str):
                char_upper = ans_val.strip().upper()
                if char_upper in letter_map:
                    selected_idx = letter_map[char_upper]
                elif ans_val.strip().isdigit():
                    selected_idx = int(ans_val.strip())
            elif isinstance(ans_val, (int, float)):
                selected_idx = int(ans_val)
            elif isinstance(ans_val, dict):
                for k, v in ans_val.items():
                    if v is True or str(v).lower() == "true":
                        if str(k) in real_keys:
                            selected_idx = real_keys.index(str(k))
                        elif str(k).isdigit():
                            selected_idx = int(k)
                        break

            if selected_idx is None or selected_idx >= len(real_keys):
                selected_idx = 0

            ans_dict = {rk: (idx == selected_idx) for idx, rk in enumerate(real_keys)}
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": ans_dict}

        elif q_type in ("multi", "true-false"):
            options = q.get("options") or {}
            real_keys = list(options.keys()) if isinstance(options, dict) else ["0", "1", "2", "3"]
            ans_dict = {}
            if isinstance(ans_val, dict):
                for idx, rk in enumerate(real_keys):
                    val = ans_val.get(rk, ans_val.get(str(idx), False))
                    ans_dict[rk] = bool(val is True or str(val).lower() == "true")
            elif isinstance(ans_val, list):
                for idx, rk in enumerate(real_keys):
                    ans_dict[rk] = bool(idx in ans_val or str(idx) in ans_val or rk in ans_val)
            else:
                ans_dict = {rk: (idx == 0) for idx, rk in enumerate(real_keys)}
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": ans_dict}

        elif q_type == "text_ai":
            if isinstance(ans_val, dict):
                text_str = str(ans_val.get("0") or next(iter(ans_val.values()), "")).strip()
            else:
                text_str = str(ans_val or "").strip()
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": {"0": text_str}}

        elif q_type == "essay":
            if isinstance(ans_val, dict):
                t_val = ans_val.get("title") or ans_val.get("titulo") or "Redação"
                b_val = ans_val.get("body") or ans_val.get("redacao") or ans_val.get("texto") or ""
            else:
                t_val = "Redação"
                b_val = str(ans_val or "")
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": {"title": str(t_val).strip(), "body": str(b_val).strip()}}

        elif q_type == "order-sentences":
            if isinstance(ans_val, list):
                s_list = [str(x) for x in ans_val]
            else:
                s_list = [str(ans_val)]
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": s_list}

        else:
            normalized[str(q_id)] = {"question_id": safe_qid, "question_type": q_type, "answer": ans_val}

    return normalized

def _is_question_answer_valid(qid: str, q_type: str, answers_dict: dict) -> bool:
    """Check if question answer meets structural requirements."""
    entry = answers_dict.get(str(qid))
    if not entry or not isinstance(entry, dict):
        return False
    ans = entry.get("answer")
    if ans is None:
        return False

    if q_type == "single":
        return isinstance(ans, dict) and sum(1 for v in ans.values() if v is True) == 1
    elif q_type in ("multi", "true-false"):
        return isinstance(ans, dict) and len(ans) > 0
    elif q_type in ("fill-words", "cloud", "order-sentences"):
        return isinstance(ans, list) and len(ans) > 0 and all(bool(str(x).strip()) for x in ans)
    elif q_type == "text_ai":
        return isinstance(ans, dict) and bool(str(ans.get("0", "")).strip())
    elif q_type == "fill-letters":
        return isinstance(ans, str) and bool(ans.strip())
    elif q_type == "essay":
        return isinstance(ans, dict) and bool(str(ans.get("body", "")).strip())
    return True

async def _solve_question_individually(q: dict, task_title: str, task_desc: str) -> Tuple[str, dict]:
    """Fallback: solve an individual question with focused concise prompt."""
    q_id = str(q.get("id"))
    q_type = q.get("type")
    stmt = _strip_html(q.get("statement", "")).replace("[...]", "").replace("...", ". ").replace("…", ". ")

    opts = q.get("options") or {}
    opts_text = ""
    if q_type == "single" and isinstance(opts, dict):
        letter_keys = ["A", "B", "C", "D", "E"]
        for idx, (k, opt) in enumerate(opts.items()):
            letter = letter_keys[idx] if idx < len(letter_keys) else str(idx)
            s = _strip_html(opt.get("statement", "") if isinstance(opt, dict) else str(opt))
            opts_text += f"Alternativa {letter}: {s}\n"
        format_instr = '{"resposta": "A"}'

    elif q_type in ("multi", "true-false") and isinstance(opts, dict):
        for k, opt in opts.items():
            s = _strip_html(opt.get("statement", "") if isinstance(opt, dict) else str(opt))
            opts_text += f"{k}) {s}\n"
        format_instr = '{"0": true, "1": false, "2": true, "3": false}'

    elif q_type == "fill-words" and isinstance(opts, dict):
        p_parts = opts.get("phrase", [])
        txt, b = "", 0
        for p in p_parts:
            if p.get("type") == "text":
                txt += p.get("value", "")
            elif p.get("type") == "select":
                b += 1
                txt += f" [LACUNA_{b}] "
        opts_text = f"Frase: {txt}\nOpções disponíveis: {', '.join(opts.get('items', []))}\n"
        format_instr = '{"palavras": ["palavra1", "palavra2", "palavra3"]}'

    elif q_type == "cloud" and isinstance(opts, dict):
        opts_text = f"Palavras disponíveis: {', '.join(opts.get('words', []))}\n"
        format_instr = '{"palavras": ["Palavra1", "Palavra2", ...]}'

    elif q_type == "text_ai" and isinstance(opts, dict):
        kw = opts.get("ai_grading_keywords", [])
        if kw:
            opts_text = f"Palavras-chave obrigatórias: {', '.join(kw)}\n"
        format_instr = '{"0": "texto dissertativo completo"}'
    else:
        format_instr = "{}"

    prompt = f"""Você é um assistente educacional brasileiro.
Responda a questão escolar da matéria "{task_title}":

Enunciado: {stmt}
{opts_text}

Responda em formato JSON:
{format_instr}"""

    try:
        raw, _ = await _call_ai_completion(prompt, timeout=20.0)
        parsed = _parse_ai_json(raw)
        return q_id, parsed
    except Exception as e:
        logger.warning(f"Individual solve failed for Q{q_id}: {e}")
        return q_id, None

async def resolve_task_answers(task_data: dict, task_id: int) -> dict:
    """Full solving pipeline: cache check -> AI API -> validation & normalizer -> save cache."""
    is_essay = task_data.get("is_essay") or task_data.get("task_is_essay") or any(
        q.get("type") == "essay" for q in task_data.get("questions", [])
    )

    cached_answers, has_all_cached = await db_call(resolve_cached_answers, task_data, task_id)
    if has_all_cached:
        logger.info(f"[AI Pipeline] Resposta 100% resolvida via cache para tarefa {task_id}")
        return {
            "success": True,
            "answers": cached_answers,
            "model_used": "db-cache",
            "raw": ""
        }

    images = _extract_images_from_task(task_data)
    questions = task_data.get("questions", [])
    answerable_questions = [q for q in questions if q.get("type") not in ("info", "section")]

    if is_essay:
        sys_prompt = "Você é um estudante brasileiro do ensino médio escrevendo uma redação escolar impecável e de nota máxima. A PRIMEIRA LINHA do seu retorno DEVE ser APENAS o Título da redação. A segunda linha em diante deve ser o corpo do texto da redação."
        prompt = _build_essay_ai_prompt(task_data)
    else:
        sys_prompt = "Você é um assistente educacional brasileiro de elite. Responda TODAS as questões escolares fornecidas rigorosamente no formato JSON solicitado."
        prompt = _build_ai_prompt(task_data)

    model_used = ""
    raw_response = ""
    try:
        raw_response, model_used = await _call_ai_completion(
            prompt, images=images, system_instruction=sys_prompt
        )
    except Exception as e:
        logger.warning(f"[AI Solver] Batch call failed: {e}")

    if is_essay:
        answers = _parse_essay_raw(raw_response, questions)
    else:
        parsed = _parse_ai_json(raw_response)
        answers = _normalize_ai_answers(parsed, task_data)

    if not is_essay:
        failed_qs = [
            q for q in answerable_questions
            if not _is_question_answer_valid(str(q.get("id")), q.get("type"), answers)
        ]
        if failed_qs:
            logger.info(f"[AI Pipeline] {len(failed_qs)} questões pendentes. Resolvendo individualmente...")
            title = task_data.get("title", "")
            desc = task_data.get("description", "")
            for q in failed_qs:
                qid, parsed_q = await _solve_question_individually(q, title, desc)
                if parsed_q:
                    norm_q = _normalize_ai_answers({qid: parsed_q}, task_data)
                    if qid in norm_q and _is_question_answer_valid(qid, q.get("type"), norm_q):
                        answers[qid] = norm_q[qid]

    if cached_answers:
        for qid, c_ans in cached_answers.items():
            answers[str(qid)] = c_ans

    if not is_essay and answers:
        await db_call(save_ai_cached_answers, task_id, answers)
        await db_call(save_question_level_ai_answers, task_data, answers)

    return {
        "success": True,
        "answers": answers,
        "model_used": model_used or "ai-auto",
        "raw": raw_response
    }
