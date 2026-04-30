# 🗳️ ElectIQ — India Election Process Education Assistant

> **PromptWars Virtual Hackathon | Hack2Skill**
> **Vertical:** Civic Education / Public Service
> **Live at:** https://electiq-l6omfhxq5a-el.a.run.app/
> **Built with:** Google Gemini 2.5 Flash · Google Cloud Run · Google Search Grounding

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/3642b16e-2c0f-450b-8dd5-4c9b618ff527" />


## 1. Chosen Vertical

**Civic Education / Public Service**

India has over 97 crore registered voters, yet awareness of the election process — how to register, what happens on polling day, how votes are counted — remains low, especially among first-time voters. ElectIQ addresses this directly: a non-partisan, AI-powered civic assistant that makes the Indian election process simple, verifiable, and accessible to every citizen.

---

## 2. Approach & Logic

### Why Gemini 2.5 Flash?
The app uses **Google Gemini 2.5 Flash** as its core AI engine — chosen for its speed, structured output support, native Google Search grounding, and Vertex AI integration on Google Cloud. Every AI feature (chat, quiz, fact-check) runs through the same `google-genai` SDK, keeping the backend clean and consistent.

### Non-Partisan by Design
The system prompt enforces strict neutrality. ElectIQ never expresses political opinions, never favors any party, and always cites official sources (ECI, NVSP, official government portals). Low temperature (0.3) is set on fact-checking calls specifically to maximize factual accuracy over creativity.

### Server-Side AI Proxy Pattern
All API keys (Gemini, Google Search) live exclusively on the Cloud Run backend. The browser never touches a key. The frontend calls `/api/chat`, `/api/fact-check`, `/api/quiz` — the Flask backend handles all AI communication. This was a deliberate security architecture decision, not an afterthought.

### Streaming for UX
The chat endpoint supports **Server-Sent Events (SSE)** streaming via `/api/chat/stream`, so responses appear token-by-token in real time — matching the experience users expect from modern AI assistants. A graceful fallback to non-streaming exists if SSE fails.

---

## 3. How the Solution Works

### Architecture

```
User Browser (SPA)
       │
       ▼
Google Cloud Run  ──► Google Artifact Registry (Docker image)
       │
       ├── /                   Serves index.html (full SPA)
       ├── /api/chat           Gemini 2.5 Flash · conversational chat
       ├── /api/chat/stream    Gemini 2.5 Flash · SSE streaming
       ├── /api/quiz           Gemini 2.5 Flash · structured JSON quiz
       ├── /api/fact-check     Gemini 2.5 Flash + Google Search Grounding
       ├── /api/search         Google Custom Search API
       └── /api/health         Health check
```

### Feature Breakdown

**🤖 AI Chat Assistant**
Conversational Q&A about any aspect of Indian elections — voter registration (Form 6, NVSP, EPIC), EVMs, VVPAT, Model Code of Conduct, NOTA, counting, government formation, and more. Full conversation history is maintained client-side and sent with each request. Markdown responses are rendered into clean HTML.

**🔍 AI Fact Checker** *(key differentiator)*
Users paste any election-related claim (e.g. *"EVMs can be hacked remotely"*). Gemini verifies it using **live Google Search grounding** and returns a structured verdict:
- `TRUE` / `FALSE` / `MISLEADING` / `UNVERIFIED`
- Plain-language explanation
- Official sources with URLs
- Related facts for context

This is the feature that separates ElectIQ from a basic chatbot — grounded, source-aware verification of election misinformation.

**🧠 AI Quiz Generator**
Freshly generated 5-question MCQs on a chosen topic (Election Process, Voter Registration, EVM/VVPAT, Model Code of Conduct). Each wrong answer includes an explanation, turning mistakes into learning moments. Questions are generated as structured JSON — parsed safely, never evaluated.

**📅 Visual Election Timeline**
A step-by-step interactive timeline of the full Indian election lifecycle — from ECI announcement and Model Code of Conduct through nomination, campaigning, polling day, EVM sealing, counting, and government formation. Filterable by phase (Pre-election / Polling / Post-election).

**🗺️ Live Elections Map**
An interactive section showing currently active and upcoming state elections in India. Users can click a state to view election type, total seats, polling date, and counting date — then jump directly into the AI assistant with that election as context.

**📆 Google Calendar Integration**
Key election milestones (Voter Registration Deadline, Polling Day, Counting Day) can be saved to Google Calendar with one click — using RFC 5545 deep links. No OAuth flow required; works for any Google account.

**🌐 Hindi Language Support**
The UI includes a language toggle (`EN / हिं`) for Hindi — addressing the accessibility needs of India's large non-English-speaking voter population.

### Google Services Used

| Service | Role | Depth |
|---|---|---|
| **Google Gemini 2.5 Flash** | Core AI — chat, quiz, fact-check | Deep |
| **Google Search Grounding** | Live web verification for fact-checker | Deep |
| **Google Cloud Run** | Containerized deployment, auto-scaling, managed TLS | Deep |
| **Google Artifact Registry** | Docker image storage | Medium |
| **Vertex AI API** | Production Gemini access via service account | Medium |
| **Google Custom Search API** | Real-time election news and resource search | Medium |
| **Google Calendar** | One-click election date saving via deep links | Light |
| **Google Fonts** | Typography (Syne + DM Sans) | Light |

### Project Structure

```
electiq/
├── app.py               # Flask backend — AI proxy, all API endpoints
├── requirements.txt     # Python dependencies (google-genai, flask, gunicorn)
├── Dockerfile           # Cloud Run container
├── deploy.sh            # One-command deployment script
├── static/
│   └── index.html       # Complete SPA — HTML + CSS + JS (~1,100 lines)
├── tests/
│   └── test_app.py      # Unit tests for all endpoints
└── README.md
```

---

## 4. Assumptions Made

1. **Target audience is Indian citizens** — content, terminology, and official links are India-specific (ECI, NVSP, Lok Sabha, Vidhan Sabha). Other countries are out of scope for this version.

2. **First-Past-the-Post is the voting system explained** — ElectIQ covers FPTP (used in Lok Sabha and Vidhan Sabha elections). Proportional/indirect systems (Rajya Sabha, Presidential) are mentioned but not the primary focus.

3. **No user accounts or persistent storage** — conversation history lives in the browser session only. No user data is stored, logged, or transmitted beyond what Gemini needs to generate a response.

---

## 🚀 Deployment

### Quick Deploy to Google Cloud Run

```bash
git clone https://github.com/OptimistOtaku/ElectIQ.git
cd ElectIQ

export GEMINI_API_KEY=your_key_here   # from aistudio.google.com
chmod +x deploy.sh
./deploy.sh your-gcp-project-id
```

### Local Development

```bash
pip install -r requirements.txt

export GEMINI_API_KEY=your_gemini_key
export GOOGLE_SEARCH_API_KEY=your_key   # optional
export GOOGLE_SEARCH_CX=your_cx         # optional

python app.py
# http://localhost:8080
```

### Run Tests

```bash
python -m pytest tests/ -v
```

---

## 🔒 Security

- API keys stored exclusively as Cloud Run environment variables — never in frontend code
- Flask backend proxies all AI requests — browser has zero direct API access
- Input validation on all endpoints (minimum length, required fields, type checks)
- Gunicorn with gthread workers in production (not Flask dev server)
- No user data stored or logged at any layer
- Cloud Run provides managed HTTPS/TLS automatically

---

## ♿ Accessibility

- Semantic HTML heading hierarchy (`h1` → `h2` → `h3`)
- WCAG AA contrast ratios throughout
- Keyboard-navigable interactive elements
- Fully responsive — mobile, tablet, desktop
- Hindi language toggle for non-English users
- Descriptive button labels (no icon-only controls)

---

*ElectIQ is strictly non-partisan. It does not promote or endorse any political party, candidate, or ideology. All content is derived from official Election Commission of India publications and public government sources.*
