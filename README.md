# Sala do Passado

Plataforma unificada para resolução inteligente de atividades escolares, redações assistidas por IA e automação do ecossistema Matific para a plataforma Sala do Futuro (SED-SP / IP.TV).

---

## ✨ Funcionalidades

- **Tarefas Objetivas**: Resolução de questões de múltipla escolha (`single`, `multi`), verdadeiro ou falso (`true-false`), preenchimento de lacunas (`fill-words`), nuvem de palavras (`cloud`), letras (`fill-letters`) e ordenação de sentenças (`order-sentences`).
- **Redações (Texto Dissertativo)**: Geração de redações escolares de alta qualidade com adequação temática, contagem de caracteres e regras estritas de humanização estilística.
- **Ecossistema Matific**:
  - Resolução automatizada de tarefas de campanha e Ilha da Aventura.
  - Execução em lote (*batch mode*) com tempos humanizados e controle de precisão.
  - Sincronização de inventário, customização de avatar/aeronave e ajuste de estatísticas.
- **Resolvedor de CAPTCHA Integrado**: Preditor local baseado em CNN (PyTorch) para resolução automática de desafios de verificação.
- **Cache Local Inteligente**: Armazenamento SQLite (`tarefas.db`) para reutilização instantânea de respostas já resolvidas.

---

## 🤖 Integração com Inteligência Artificial

A plataforma se comunica com qualquer provedor de IA que exponha uma **API compatível com o padrão OpenAI** (`/v1/chat/completions`).

### Sugestão de Provedores Gratuitos (ex: OmniRoute)

Caso queira utilizar modelos gratuitos de alta performance, você pode usar um gateway OpenAI-compatible (como o **OmniRoute**) configurado com provedores web reversos:

1. **DeepSeek Web (Recomendado)**: `ds-web/deepseek-v4-flash-think` (DeepSeek V4 Flash Thinking)
2. **Gemini Web**: `gemini-web/gemini-3.6-flash` (Gemini 3.6 Flash)
3. **Claude Web**: `claude-web/claude-5-sonnet` (Claude 5 Sonnet)
4. **OpenCode Free**: `oc/nemotron-3-ultra-free` ou outros modelos gratuitos do OpenCode

---

## 🚀 Instalação e Configuração

### 1. Pré-requisitos
- Python 3.10 ou superior
- Pip e suporte a ambientes virtuais

### 2. Clonar o repositório e preparar o ambiente

```bash
git clone https://github.com/seu-usuario/saladopassado.git
cd saladopassado

# Criar e ativar o ambiente virtual
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar as dependências
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente

Copie o arquivo de exemplo `.env.example` para `.env` e configure conforme seu ambiente:

```bash
cp .env.example .env
```

Principais variáveis configuráveis no `.env`:

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `AI_BASE_URL` | `http://127.0.0.1:20128/v1` | URL base do provedor de IA compatível com OpenAI (`/v1`) |
| `AI_API_KEY` | `""` | Chave de API do provedor (opcional se local) |
| `AI_MODEL` | `ds-web/deepseek-v4-flash-think` | Modelo principal para resolução de tarefas |
| `AI_FALLBACK_MODEL` | `gemini-web/gemini-3.6-flash` | Modelo de contingência |
| `AI_CLAUDE_MODEL` | `claude-web/claude-5-sonnet` | Modelo para redações complexas |
| `CANDIDATE_MODELS` | Lista ordenada de modelos | Ordem de fallback para tentativas automáticas |
| `PROXY` | `""` | Proxy HTTP/HTTPS opcional (Recomendado: proxy residencial ou IP brasileiro porque a CDN bloqueia IPs não brasileiros, e na maioria dos casos datacenter também) |
| `CAPTCHA_SOLVER_PYTHON` | `python3` | Executável Python para rodar o preditor de CAPTCHA |
| `DB_PATH` | `tarefas.db` | Caminho do arquivo SQLite local |

---

## 💻 Executando a Aplicação

Inicie o servidor backend FastAPI:

```bash
python3 app.py
```

Ou diretamente via Uvicorn:

```bash
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

Abra seu navegador em [http://localhost:8080](http://localhost:8080) para acessar a interface da plataforma.

---

## 📁 Estrutura do Projeto

```text
├── app.py                 # Servidor principal FastAPI e rotas de API
├── ai_solver.py           # Pipeline de resolução de tarefas e redações via IA
├── captcha/
│   ├── best.pt            # Pesos treinados da rede neural para CAPTCHA
│   ├── captcha_cnn.py     # Arquitetura da CNN PyTorch
│   └── predict_captcha.py # Script de inferência de CAPTCHA
├── captcha_solver.py      # Loop de desafio e verificação de CAPTCHA
├── client.py              # Cliente HTTP com suporte a TLS spoofing e proxy
├── config.py              # Carregamento centralizado de configurações e prompts
├── database.py            # Gerenciamento do banco de dados SQLite local
├── matific_client.py      # Cliente de automação e telemetria do Matific
├── static/                # Arquivos estáticos (CSS, JS)
├── templates/             # Templates HTML da interface
├── .env.example           # Modelo de arquivo de configuração
├── .gitignore             # Arquivos e diretórios ignorados pelo Git
└── requirements.txt       # Dependências do projeto
```

---

## ⚠️ Aviso Legal

Este projeto foi desenvolvido estritamente para fins educacionais e de pesquisa sobre segurança de APIs, arquitetura de sistemas e automação. O uso é de responsabilidade exclusiva do usuário.
