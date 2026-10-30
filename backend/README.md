# Bolo Backend (FastAPI)

FastAPI server for **Bolo**, a voice-first government schemes helper for rural and semi-urban India. Deployable as a standalone project to Vercel Serverless.

## Features
- **In-Memory Pure-Python TF-IDF Vector Search**: Sublinear TF, IDF, and Cosine similarity across 130 verified welfare schemes without heavy dependencies (no scikit-learn, numpy, or PyTorch; adheres to Vercel serverless size limits).
- **Open-Source / Open-Weight Models**:
  - Speech-To-Text: `whisper-large-v3` via Groq.
  - LLM: `openai/gpt-oss-120b` (or active open-weight model on Groq).
- **Voice Intelligence**:
  - Auto language detection and mislabel correction for Indic languages (e.g. Telugu, Hindi).
  - Natural spoken Telugu (vyavaharika) and spoken Hindi (bolchal).
- **Eligibility Helper**:
  - Multi-turn conversation awareness with at most 3 targeted follow-up questions before determining final eligibility.
  - Strictly grounded in official scheme data.

## Environment Variables
Create a `.env` file or export in your terminal:
```bash
GROQ_API_KEY=your_groq_api_key_here
```

## Running Locally
1. Create and activate a Python 3.12 virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
4. Access endpoints:
   - Health check: `http://127.0.0.1:8000/health`
   - Schemes: `http://127.0.0.1:8000/schemes`
   - Categories: `http://127.0.0.1:8000/categories`
   - Interactive Docs: `http://127.0.0.1:8000/docs`

## Running Tests
Run the standalone test suite (Python standard library only):
```bash
python test_api.py
```

## Vercel Deployment
- **Root Directory**: `backend`
- **Environment Variables**: `GROQ_API_KEY`
- The `app` instance in `main.py` is automatically served by Vercel's Python runtime.
