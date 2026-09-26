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
- **LeiaSP**: Leitura humanizada de livros com telemetria Colibrio e resolução automática de quizzes via IA.
- **Suporte multi-usuário**: isolamento total por conta — cada aluno vê apenas suas tarefas, episódios, livros e logs de execução (detalhes abaixo).

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

## 👥 Suporte multi-usuário

Vários alunos podem usar o mesmo backend (inclusive em sequência na mesma aba) sem vazar dados entre contas:

- **Cache de tarefas por conta**: o detalhe de cada tarefa (`answer_id`, tentativa) é chaveado por `(usuário, task_id)`.
- **Jobs e lotes com dono**: execuções agendadas, lotes de tarefas, simulações Matific e leituras LeiaSP retornam `403` para qualquer usuário que não seja o dono.
- **Workers congelam as credenciais**: jobs em background continuam agindo como o usuário que os criou, mesmo após logout ou login de outra conta.
- **Frontend limpa tudo ao trocar de conta**: estado, polls, banners, modais, logs e formulário de login são resetados; respostas atrasadas da conta anterior são ignoradas (proteção contra race).
- **Sessões com validade de 24h**: sessões expiradas são invalidadas e expurgadas automaticamente; o logout também limpa o cache Matific e de tarefas do usuário.
- **Sem credenciais no repositório**: scripts auxiliares (`auto_runner.py`, `batch_worker.py`) leem credenciais apenas de variáveis de ambiente — nunca commite RA/senha reais.

### Concorrência das tarefas

A abertura da tarefa, a resolução do CAPTCHA e a consulta à IA compartilham um
semáforo de **5 preparações simultâneas por processo do servidor**, entre todos
os usuários, lotes e acessos individuais. Lotes maiores são aceitos e as tarefas
excedentes aparecem como **Na fila**. A vaga é liberada antes do tempo de espera
e do envio das respostas. Se o envio precisar reabrir a tarefa para atualizar o
`answer_id`, somente essa reabertura ocupa uma vaga; o POST/PUT das respostas
continua sem limite de concorrência. Parar um lote impede que tarefas na fila
iniciem a abertura ou a consulta à IA.

Os enunciados passam pelo DOMPurify, servido localmente, para preservar HTML de
conteúdo (como imagens e tabelas) removendo scripts e atributos ativos. Os demais
textos externos e logs são escapados ou inseridos como texto.

Variáveis de ambiente dos scripts auxiliares:

| Variável | Usada por | Descrição |
| :--- | :--- | :--- |
| `SALADOPASSADO_RA`, `SALADOPASSADO_PASSWORD` | `auto_runner.py`, `batch_worker.py` | Credenciais dos runners manuais (obrigatórias) |

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

## Testes de concorrência e segurança da interface

Os testes usam respostas simuladas e não acessam as plataformas externas.
Para executar os testes de backend e de navegador:

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

Para executar somente os testes de concorrência com as dependências do backend:

```bash
python -m unittest discover -s tests -p "test_task_concurrency.py" -v
```

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
├── leiasp_client.py         # Cliente de automação e telemetria do LeiaSP
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

---

## 📬 Contato

Dúvidas, sugestões ou suporte: **desconfia.company@proton.me**
