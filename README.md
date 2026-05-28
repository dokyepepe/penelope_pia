# Penélope

**Assistente Pessoal de IA Local · Estilo Jarvis · Windows 11**

Sistema 100% offline, sempre ativo, com reconhecimento de voz, controle do Windows e múltiplos perfis de acesso.

---

## Pré-requisitos

| Componente | Requisito |
|---|---|
| **Python** | 3.11+ |
| **OS** | Windows 11 (10 compatível) |
| **RAM** | 16 GB (mínimo) |
| **GPU** | NVIDIA RTX 3060+ (8GB VRAM) — opcional, modo CPU suportado |
| **Microfone** | Qualquer microfone USB ou integrado |
| **Ollama** | Instalado e rodando ([ollama.com](https://ollama.com)) |

## Instalação

```bash
# 1. Clone o repositório
git clone <repo-url>
cd penelope_pia

# 2. Crie um ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 3. Instale as dependências
pip install -e .

# 4. Instale e configure o Ollama
# Baixe em https://ollama.com e execute:
ollama pull llama3.1:8b

# 5. (Opcional) Instale o Piper TTS para voz natural
# Baixe em https://github.com/rhasspy/piper/releases
```

## Como Executar

```bash
# Opção 1: via entry point
penelope

# Opção 2: via módulo Python
python -m penelope.main

# Opção 3: com debug verbose
python -m penelope.main --debug
```

No primeiro boot, o **Setup Wizard** vai pedir seu nome e frase-chave de acesso.

## Uso Básico

1. Diga **"Penélope"** (ou pressione `Alt+Space`)
2. Fale sua **frase-chave** para autenticação
3. Dê um **comando por voz**:
   - *"Penélope, abre o Chrome"*
   - *"Penélope, aumenta o volume"*
   - *"Penélope, que horas são?"*
   - *"Penélope, captura a tela"*
   - *"Penélope, modo trabalho"*

Se o Whisper STT não estiver disponível, o sistema entra em **modo texto** (digita comandos no terminal).

## Estrutura do Projeto

```
penelope_pia/
├── config/
│   ├── settings.yaml        # Configurações centrais
│   └── personas.yaml        # Personas por perfil
├── penelope/
│   ├── main.py               # Entry point (orquestrador)
│   ├── ai/                   # LLM, intent parser, memória
│   ├── auth/                 # Autenticação e perfis
│   ├── core/                 # Event bus, executor, setup
│   ├── persistence/          # Watchdog, health, service
│   ├── system/               # Controle do Windows
│   ├── ui/                   # HUD, radial menu, tray
│   ├── utils/                # Utilitários
│   └── voice/                # Wake word, STT, TTS
├── pyproject.toml
└── requirements.txt
```

## Dados e Logs

```
C:\Penelope\
├── data\
│   ├── profiles.db           # Perfis de usuário (criptografado)
│   ├── sessions.db           # Histórico de sessões
│   ├── clipboard.db          # Histórico de clipboard
│   ├── chroma\               # Memória vetorial (ChromaDB)
│   └── screenshots\          # Capturas de tela
└── logs\
    ├── penelope.log           # Log principal (rotação diária)
    ├── crash.log              # Erros e crashes
    └── watchdog.log           # Saúde dos processos
```

## Perfis de Acesso

| Nível | Nome | Acesso |
|---|---|---|
| 1 | **Proprietário** | Total — gerencia outros usuários |
| 2 | **Coproprietário** | Amplo — definido pelo proprietário |
| 3 | **Usuário Comum** | Básico — apps, volume, perguntas |

## Licença

Proprietário · Pietro Nogueira · 2025–2026