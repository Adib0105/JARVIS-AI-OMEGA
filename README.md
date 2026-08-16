# JARVIS AI OMEGA

> **A text-first, tool-using personal AI agent created by Adib Azam.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Model](https://img.shields.io/badge/OpenAI-GPT--5.6-black)
![License](https://img.shields.io/badge/License-MIT-green)
![Voice](https://img.shields.io/badge/Voice-Not%20installed-lightgrey)

JARVIS AI OMEGA is a public, portfolio-grade personal AI project focused on **high-quality text interaction first**. It combines OpenAI's Responses API with configurable high reasoning, web search, Code Interpreter, persistent local memory, multi-step custom tool calling, safe local file intelligence, and a permission-gated Windows action layer.

**Creator identity:** if you ask the custom assistant who built this JARVIS project, it answers that it was created by **Adib Azam** while still correctly distinguishing the JARVIS application from its underlying AI provider.

## What makes OMEGA different

- **GPT-5.6 brain** by default
- **xhigh reasoning** configurable through `.env`
- **Multi-step agent loop**: plan → tool use → verify → answer
- **Live web search** for fresh public information
- **Hosted Code Interpreter** for calculations, Python, and data analysis
- **Persistent SQLite memory** with sessions and reusable user facts
- **Hinglish + English auto style matching**
- **Safe local file intelligence** for Desktop, Documents, Downloads, and the project directory
- **Permission gate** before privacy-sensitive/local actions
- **Windows app launcher** limited to an explicit allowlist
- **No arbitrary host shell**
- **No credential extraction, file deletion, stealth control, or security bypass tools**
- **Rich terminal UI** with commands, panels, status, and local approvals
- **Python 3.14 friendly dependency set** — no PyAudio/native voice stack in this release
- **Automated CI** on multiple Python versions

## Architecture

```mermaid
flowchart TD
    U[User - Text] --> UI[Rich CLI]
    UI --> CORE[JARVIS OMEGA Core]
    CORE --> MODEL[GPT-5.6 Responses API]
    MODEL --> WEB[Web Search]
    MODEL --> CODE[Code Interpreter]
    MODEL --> TOOLS[Custom Function Tools]
    TOOLS --> GATE[Permission Gate]
    GATE --> MEM[SQLite Memory]
    GATE --> FILES[Read-only Local Files]
    GATE --> SYS[System Info / App & URL Launch]
    MEM --> CORE
    FILES --> CORE
    SYS --> CORE
```

## Project structure

```text
JARVIS-AI-OMEGA/
├── jarvis/
│   ├── config.py
│   ├── core.py
│   ├── local_files.py
│   ├── memory.py
│   ├── permissions.py
│   ├── prompt.py
│   ├── system_tools.py
│   ├── tools.py
│   └── ui.py
├── tests/
├── .github/workflows/ci.yml
├── .env.example
├── main.py
├── self_check.py
├── setup_windows.ps1
├── run_jarvis.bat
└── requirements.txt
```

## Windows quick start

Open PowerShell inside the cloned repository:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Then open `.env` and set:

```env
OPENAI_API_KEY=your_key_here
```

Validate the installation:

```powershell
.\.venv\Scripts\python.exe self_check.py
```

Start JARVIS:

```powershell
.\.venv\Scripts\python.exe main.py
```

Or double-click `run_jarvis.bat`.

## Example prompts

```text
Tumhe kisne banaya?
Explain neural networks in Hinglish like I am a CST student.
Latest AI news search karke 5 important points batao.
Calculate a 5-year SIP projection with Python.
Remember that I prefer concise Hinglish answers.
Mere Downloads me resume naam ki file search karo.
Is Python file ko read karke bugs batao.
Calculator kholo.
```

## Built-in slash commands

| Command | Purpose |
|---|---|
| `/help` | Show command list |
| `/new` | Start a new conversation session |
| `/status` | Show model, tools, reasoning mode and current session |
| `/remember <text>` | Store a local long-term fact |
| `/recall <query>` | Search local long-term memory |
| `/sessions` | Show recent sessions |
| `/exit` | Exit JARVIS |

## Safety model

OMEGA is intentionally powerful **without giving the model unrestricted control of the host PC**.

Local actions such as reading a file, searching local folders, opening a URL, or launching an app can require explicit confirmation. Local file reads are restricted to configured roots and safe text/code extensions. Secret-like paths are blocked. The agent does not expose arbitrary shell execution, passwords, credential scraping, deletion, installation, persistence, or security-bypass functions.

This makes the project useful for real work while keeping computer access understandable and auditable.

## Configuration

`.env.example` includes:

- `OPENAI_MODEL=gpt-5.6`
- `REASONING_EFFORT=xhigh`
- web search on/off
- Code Interpreter on/off
- local tools on/off
- local approval requirement
- maximum tool rounds
- memory history size
- allowed local file roots

## Roadmap

### Current release — Text Core
- [x] Advanced text chat
- [x] Web search
- [x] Code Interpreter
- [x] Local long-term memory
- [x] Multi-tool agent loop
- [x] Permission-gated local tools
- [x] Public-ready documentation and CI

### Future releases
- [ ] Streaming text UI
- [ ] Optional desktop/web dashboard
- [ ] Document ingestion and semantic knowledge base
- [ ] Plugin/skill marketplace layer
- [ ] Calendar and email connectors
- [ ] Screen vision module
- [ ] **Voice / wake word / realtime speech — intentionally deferred**

## Security

Please read [SECURITY.md](SECURITY.md). Never commit your `.env` or API key.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License — see [LICENSE](LICENSE).

---

**JARVIS AI OMEGA — Created by Adib Azam**
