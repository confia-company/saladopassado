import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SED and IPTV Endpoints
SED_LOGIN_URL = os.environ.get(
    "SED_LOGIN_URL",
    "https://sedintegracoes.educacao.sp.gov.br/saladofuturobffapi/credenciais/api/LoginCompletoToken"
)
SED_VALIDA_URL = os.environ.get(
    "SED_VALIDA_URL",
    "https://sedintegracoes.educacao.sp.gov.br/saladofuturobffapi/credenciais/api/ValidarToken"
)
SED_SUBSCRIPTION_KEY = os.environ.get("SED_SUBSCRIPTION_KEY", "d701a2043aa24d7ebb37e9adf60d043b")

IPTV_BASE_URL = os.environ.get("IPTV_BASE_URL", "https://edusp-api.ip.tv")
IPTV_TOKEN_URL = os.environ.get("IPTV_TOKEN_URL", f"{IPTV_BASE_URL}/registration/edusp/token")

# Proxy Configuration (Optional: Recommended residential proxy or Brazilian IP proxy)
PROXY = os.environ.get("PROXY", os.environ.get("RESIDENTIAL_PROXY", os.environ.get("HTTP_PROXY", "")))
RESIDENTIAL_PROXY = PROXY  # Alias for backward compatibility

# AI Provider (OpenAI-compatible API endpoint)
AI_BASE_URL = os.environ.get(
    "AI_BASE_URL",
    os.environ.get("OPENAI_BASE_URL", os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1"))
)
AI_API_KEY = os.environ.get("AI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

AI_MODEL = os.environ.get(
    "AI_MODEL",
    os.environ.get("OPENAI_MODEL", os.environ.get("OMNIROUTE_MODEL", "ds-web/deepseek-v4-flash-think"))
)
AI_FALLBACK_MODEL = os.environ.get(
    "AI_FALLBACK_MODEL",
    os.environ.get("OMNIROUTE_FALLBACK_MODEL", "gemini-web/gemini-3.6-flash")
)
AI_CLAUDE_MODEL = os.environ.get(
    "AI_CLAUDE_MODEL",
    os.environ.get("OMNIROUTE_CLAUDE_MODEL", "claude-web/claude-5-sonnet")
)

# Aliases for backward compatibility
OMNIROUTE_BASE_URL = AI_BASE_URL
OMNIROUTE_MODEL = AI_MODEL
OMNIROUTE_FALLBACK_MODEL = AI_FALLBACK_MODEL
OMNIROUTE_CLAUDE_MODEL = AI_CLAUDE_MODEL

candidate_models_env = os.environ.get("CANDIDATE_MODELS", "")
if candidate_models_env:
    CANDIDATE_MODELS = [m.strip() for m in candidate_models_env.split(",") if m.strip()]
else:
    CANDIDATE_MODELS = [
        AI_MODEL,
        AI_FALLBACK_MODEL,
        AI_CLAUDE_MODEL,
        "ds-web/deepseek-chat",
        "ds-web/deepseek-reasoner",
        "oc/nemotron-3-ultra-free",
    ]

DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "tarefas.db"))

# CAPTCHA Solver Configuration
CAPTCHA_SOLVER_PYTHON = os.environ.get("CAPTCHA_SOLVER_PYTHON", "python3")
CAPTCHA_PREDICT_SCRIPT = os.environ.get(
    "CAPTCHA_PREDICT_SCRIPT",
    os.path.join(BASE_DIR, "captcha", "predict_captcha.py")
)
CAPTCHA_MODEL_WEIGHTS = os.environ.get(
    "CAPTCHA_MODEL_WEIGHTS",
    os.path.join(BASE_DIR, "captcha", "best.pt")
)

TASK_PROMPT_TEMPLATE = """Você é um assistente educacional brasileiro extremamente inteligente.
Responda TODAS as questões escolares abaixo com 100% de exatidão.

TAREFA: {{TITLE}}
DESCRIÇÃO: {{DESCRIPTION}}

IMPORTANTE: Retorne APENAS um único objeto JSON válido onde cada chave é exatamente o ID da questão (ex: "448526375").
Formato esperado para cada tipo de questão:

- "single": {"question_id": ID, "question_type": "single", "answer": {"0": false, "1": true, "2": false, "3": false}} (exatamente UMA opção true)
- "multi": {"question_id": ID, "question_type": "multi", "answer": {"0": true, "1": false, "2": true}}
- "true-false": {"question_id": ID, "question_type": "true-false", "answer": {"0": true, "1": false, "2": true, "3": false}}
- "fill-words": {"question_id": ID, "question_type": "fill-words", "answer": ["palavra_lacuna_1", "palavra_lacuna_2", ...]}
- "cloud": {"question_id": ID, "question_type": "cloud", "answer": ["Palavra1", "Palavra2", ...]} (Ordene as palavras disponíveis para formar a frase correta)
- "text_ai": {"question_id": ID, "question_type": "text_ai", "answer": {"0": "texto dissertativo completo"}}
- "fill-letters": {"question_id": ID, "question_type": "fill-letters", "answer": ["a", "b", "c"]} ou "palavra"
- "order-sentences": {"question_id": ID, "question_type": "order-sentences", "answer": ["Texto exato da sentença 1", "Texto exato da sentença 2", ...]}

QUESTÕES A RESOLVER:
{{QUESTIONS_SECTION}}

RESPONDA EXCLUSIVAMENTE COM O JSON VÁLIDO:"""

ESSAY_PROMPT_TEMPLATE = """Você é um estudante brasileiro do ensino médio escrevendo uma redação escolar impecável e de nota máxima.

PROPOSTA / TEMA DA REDAÇÃO: {{TITLE}}
GÊNERO TEXTUAL: {{GENRE_STATEMENT}}
DESCRIÇÃO/PROPOSTA: {{DESCRIPTION}}
LIMITE DE CARACTERES: Mínimo de {{MIN_WORDS}} e máximo de {{MAX_WORDS}} {{TEXT_COUNT_UNIT}}s (contando espaços e pontuações). O texto gerado DEVE caber estritamente dentro deste limite de caracteres!

TEXTOS DE APOIO / COLETÂNEA:
{{SUPPORT_TEXT}}

CRITÉRIOS DE AVALIAÇÃO E RUBRICAS:
{{SKILLS_TEXT}}

{{HUMANIZE_INSTRUCTIONS}}

IMPORTANTE - REGRAS DO FORMATO DE RETORNO DA RESPOSTA:
1. Sua resposta deve conter exatamente o título e o corpo da redação.
2. A PRIMEIRA LINHA do seu retorno DEVE ser APENAS o Título da redação. NÃO inclua nenhum rótulo, marcador, aspas, "Título:" ou texto extra na primeira linha. Apenas o título puro.
3. A segunda linha em diante deve ser o corpo do texto da redação, organizado em parágrafos de forma fluida.
4. Responda APENAS com a redação escrita, sem explicações extras, introduções ou conversas.

Retorne o título na primeira linha e o corpo nas linhas seguintes:"""

ESSAY_HUMANIZE_INSTRUCTIONS = """REGRAS OBRIGATÓRIAS DE ESTILO E HUMANIZAÇÃO:
- O texto DEVE parecer escrito por um estudante brasileiro comum do ensino médio.
- Mantenha o tom natural, use linguagem simples e direta.
- Varie o tamanho das frases (misture curtas e médias).
- Evite palavras excessivamente formais ou rebuscadas — troque por sinônimos comuns.
- Pequenos coloquialismos leves e erros naturais (ex: "pra" em vez de "para", "tá" em vez de "está") são bem-vindos para soar autêntico.
- Nunca use bullet points, listas, tópicos ou qualquer formatação especial.
- Nunca comece frases com conectivos formais e manjados como "Além disso,", "Portanto,", "Outrossim,", "Ademais,", "Em suma,".
- Não use voz passiva. Escreva em primeira ou terceira pessoa de forma natural e fluida."""

TEXT_AI_HUMANIZE_INSTRUCTIONS = """REGRAS DE ESTILO/HUMANIZAÇÃO OBRIGATÓRIAS (escreva como um estudante brasileiro do ensino médio):
- Linguagem simples, direta e tom natural.
- Varie o tamanho das frases (mescle curtas e médias).
- Evite termos excessivamente rebuscados ou formais (prefira sinônimos comuns).
- Coloquialismos leves e naturais (ex: 'pra' em vez de 'para', 'tá' em vez de 'está') são bem-vindos para autenticidade.
- Nunca use bullet points, tópicos, listas ou formatação markdown (como **negrito** ou *itálico*).
- Escreva em primeira ou terceira pessoa de maneira fluida, sem conectivos artificiais no início das frases (como 'Além disso', 'Portanto', 'Outrossim')."""
