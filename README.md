# Bolo (బోలో • बोलो) - Voice-First Government Schemes Help-Desk

> **Hacktoberfest Open-Source AI Project**: Empowering rural and semi-urban Indian citizens (many with low literacy and slow internet) to discover and understand government welfare schemes by talking in their own language.

**Bolo** behaves like a kind, patient village help-desk volunteer at a Gram Panchayat, **not** like a boring form or a plain chatbot. Built with 100% open-source / open-weight models, sublinear TF-IDF retrieval, and zero heavy dependencies so that it deploys effortlessly to Vercel Serverless.

---

## 🏛️ System Architecture

```text
                                  +---------------------------------------+
                                  |         User (Mobile Browser)         |
                                  |    Rural / Semi-Urban Indian Citizen  |
                                  +-------------------+-------------------+
                                                      |
                                          Voice / Audio (WebM / MP4)
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |         FastAPI Backend (/ask-voice)  |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      Whisper Large-v3 (via Groq)      |
                                  |  - Automatic Language Detection       |
                                  |  - Remaps Kannada/Tamil/Urdu -> Te/Hi |
                                  |  - Unicode Script Verification        |
                                  +-------------------+-------------------+
                                                      |
                                           Transcribed User Query
                                           (Telugu / Hindi / English)
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |   Query Generation (Open LLM, Temp 0) |
                                  |   Converts conversation context into  |
                                  |   one standalone English search query |
                                  +-------------------+-------------------+
                                                      |
                                            English Search Query
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |    Lightweight In-Memory Retrieval    |
                                  |  - Pure-Python TF-IDF & Cosine Sim    |
                                  |  - Sublinear TF + Smoothed IDF        |
                                  |  - Searches 130 Verified Schemes      |
                                  +-------------------+-------------------+
                                                      |
                                           Top 3-4 Relevant Schemes
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |       Open-Weight LLM (Groq)          |
                                  |       (openai/gpt-oss-120b)           |
                                  |  - Kind Village Volunteer Persona     |
                                  |  - Spoken Telugu (vyavaharika) &      |
                                  |    Spoken Hindi (bolchal)             |
                                  |  - Multi-turn Eligibility Helper      |
                                  |  - Grounded strictly in scheme data   |
                                  +-------------------+-------------------+
                                                      |
                                    Structured JSON Answer / Follow-up Question
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |       Frontend Mobile Web App         |
                                  |  - Web Audio Reactive Voice Orb       |
                                  |  - Text-To-Speech (SpeechSynthesis)   |
                                  |  - Tappable Options & Source Links    |
                                  |  - Interactive Documents Checklist    |
                                  +---------------------------------------+
```

---

## 🤖 Models Used (Open-Source / Open-Weight ONLY)

All inference runs via Groq using open weights. No closed models (no OpenAI closed models, no Gemini):

1. **Speech-To-Text (STT)**:
   - Model: `whisper-large-v3`
   - Handles accented Indian English, Hindi, and Telugu.
   - Detects mislabeled dialects (e.g., re-transcribes when Hindi is misclassified as Urdu/Punjabi or Telugu as Kannada/Tamil).
2. **Language Model (LLM)**:
   - Model: `openai/gpt-oss-120b` (open-weight model hosted on Groq).
   - In-memory fallback handler verifies available open models via Groq API.
   - Operates in two stages:
     - **Stage 1 (Temp 0.0)**: Conversational search query generation into standalone English keywords.
     - **Stage 2 (Temp 0.3)**: Grounded multi-turn conversational answer generation with local village volunteer phrasing.

---

## ⚡ Why Pure-Python Lightweight Retrieval?

Standard ML vector libraries (`scikit-learn`, `numpy`, `torch`, `sentence-transformers`) inflate package sizes by **hundreds of megabytes**, exceeding **Vercel Serverless deployment limits (50 MB zipped)** and causing cold-start delays.

Bolo employs an **in-memory pure-Python TF-IDF vector retrieval engine**:
- **Zero heavy dependencies**: standard library only (`math`, `re`, `collections.Counter`).
- **Sublinear term frequency**: $1 + \ln(\text{count})$ to prevent long scheme descriptions from dominating.
- **Smoothed inverse document frequency**: $\ln(1 + \frac{N}{1 + \text{df}}) + 1$.
- **Fast Startup**: Indexes all 130 verified welfare schemes in under **35 milliseconds**.
- **Cold-Start Proof**: Runs instantly with negligible memory footprint on serverless runtimes.
- Dense embedding vector search can be attached later via a vector database if needed without breaking this API contract.

---

## 📁 Repository Structure

```text
bolo/
├── backend/
│   ├── main.py              # FastAPI application & pure-Python retrieval engine
│   ├── schemes.json         # 130 verified government schemes (read-only, never modified)
│   ├── requirements.txt     # fastapi, uvicorn, groq, python-multipart ONLY
│   ├── .python-version      # 3.12
│   ├── .env.example         # Template for GROQ_API_KEY
│   ├── test_api.py          # Standalone test suite (Python standard library only)
│   ├── vercel.json          # Serverless route rewrites for Vercel
│   └── README.md            # Backend specific documentation
├── frontend/
│   ├── index.html           # Accessible mobile-first HTML shell
│   ├── styles.css           # Warm Indian palette, dark mode, animations
│   ├── app.js               # Voice orb, Web Audio VAD, barge-in, TTS, tabs
│   ├── config.js            # Central API configuration (LOCAL_API vs PROD_API)
│   ├── manifest.json        # PWA manifest
│   ├── sw.js                # Service worker caching static app shell only
│   └── icon.svg             # Bolo village help-desk volunteer vector avatar
├── .gitignore               # venv, __pycache__, .env ignored
├── LICENSE                  # MIT License
└── README.md                # Comprehensive documentation
```

---

## 🚀 Running Locally

### Step 1: Start the Backend (Port 8000)

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (fastapi, uvicorn, groq, python-multipart ONLY)
pip install -r requirements.txt

# Export your Groq API Key
export GROQ_API_KEY="your_actual_groq_api_key"

# Start FastAPI with live reload
uvicorn main:app --reload --port 8000
```

Verify backend health at `http://127.0.0.1:8000/health`.

### Step 2: Run the API Verification Suite

In a separate terminal:
```bash
cd backend
python3 test_api.py
```
This tests `GET /health`, `GET /categories`, `GET /schemes`, English eligibility query (with follow-up flow), Hindi query, Telugu query, auto-detect script query, and out-of-scope query.

### Step 3: Serve the Frontend (Port 5500)

In another terminal:
```bash
# Navigate to frontend directory
cd frontend

# Serve static files locally on port 5500
python3 -m http.server 5500
```

Open your browser at **`http://localhost:5500`**. The app is pre-configured to communicate seamlessly with `http://127.0.0.1:8000`.

---

## 🚢 Deploying to Vercel (Two Independent Projects)

Deploy both projects from the **same GitHub repository** using Vercel's multi-project root directory support.

### Project 1: Backend API (FastAPI Serverless)

1. Go to [vercel.com](https://vercel.com) and click **"Add New Project"**.
2. Select your `bolo` GitHub repository.
3. In **Project Settings**:
   - **Project Name**: `bolo-backend`
   - **Framework Preset**: `Other`
   - **Root Directory**: Click "Edit" and set to `backend`.
4. In **Environment Variables**:
   - Add `GROQ_API_KEY` = `your_actual_groq_api_key`
5. Click **Deploy**.
6. Copy the deployed domain URL (e.g. `https://bolo-backend.vercel.app`).

### Project 2: Frontend Web App (Static App Shell)

1. Click **"Add New Project"** in Vercel.
2. Select the **same** `bolo` GitHub repository.
3. In **Project Settings**:
   - **Project Name**: `bolo-frontend`
   - **Framework Preset**: `Other`
   - **Root Directory**: Click "Edit" and set to `frontend`.
   - **Build Command**: Leave empty (no build step required).
   - **Output Directory**: Leave empty.
4. Open `frontend/config.js` in your code editor and paste your deployed backend URL:
   ```javascript
   const LOCAL_API = "http://127.0.0.1:8000";
   const PROD_API = "https://bolo-backend.vercel.app"; // <-- Paste here (no trailing slash)
   ```
5. Commit and push `frontend/config.js` to GitHub. Vercel will automatically redeploy the frontend.
6. Open your frontend deployment URL on any phone or desktop browser!

---

## ⚠️ Configuration Notes

- **Helpline Number**: At the top of `backend/main.py`, replace `HELPLINE = "1800-XXX-XXXX"` with your verified state or national helpline number (e.g. `14447` or `1800-11-0001`).
- **Backend URL**: In `frontend/config.js`, set `PROD_API` to your deployed backend URL when deploying live.
- **Privacy First**: No user audio, transcripts, or personal credentials are ever saved to disk or persistent databases.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
