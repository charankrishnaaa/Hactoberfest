"""Bolo Backend: Multilingual Voice & Text Assistant for Indian Government Services."""
import os
import json
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from groq import Groq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------- Environment & Configuration ----------
def load_env():
    """Load key-value pairs from .env if present and not already set in environment."""
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception as e:
            print(f"Warning: Failed to parse .env file: {e}")

load_env()

# Models & Language setup
LLM_MODEL = "openai/gpt-oss-20b"
STT_MODEL = "whisper-large-v3"       # OpenAI Whisper open-source STT hosted on Groq
LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu"}

# Official citizen / farmer helpline
HELPLINE = "1800-180-1551"
FALLBACK = {
    "en": f"Sorry, I don't have a reliable answer. Please call the citizen helpline {HELPLINE} or visit your nearest CSC / Mee Seva centre.",
    "hi": f"माफ़ कीजिए, मेरे पास इसका पक्का जवाब नहीं है। कृपया नागरिक हेल्पलाइन {HELPLINE} पर कॉल करें या नज़दीकी CSC केंद्र जाएँ।",
    "te": f"క్షమించండి, దీనికి నా దగ్గర ఖచ్చితమైన సమాధానం లేదు. దయచేసి పౌర హెల్ప్‌లైన్ {HELPLINE} కు కాల్ చేయండి లేదా దగ్గరలోని CSC / మీ సేవా కేంద్రానికి వెళ్లండి.",
}

def get_groq_client() -> Groq:
    """Instantiate Groq client with clear error if API key is not configured."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY environment variable is not set. Please export GROQ_API_KEY or define it in a .env file."
        )
    return Groq(api_key=api_key)

# ---------- Schemes Data Loading & Normalization ----------
def load_schemes_data() -> List[Dict[str, Any]]:
    """
    Load schemes.json generically.
    Supports a root JSON list [...], or an object containing a list (e.g. {"schemes": [...]}).
    Handles arbitrary field names gracefully.
    """
    schemes_file = Path(__file__).resolve().parent / "schemes.json"
    if not schemes_file.is_file():
        return []

    try:
        content = schemes_file.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as e:
        print(f"Error loading schemes.json: {e}")
        return []

    if isinstance(data, list):
        schemes = data
    elif isinstance(data, dict):
        schemes = None
        # Check standard dictionary keys first
        for key in ["schemes", "data", "items", "records", "results"]:
            if key in data and isinstance(data[key], list):
                schemes = data[key]
                break
        # Check any dictionary key that holds a list
        if schemes is None:
            for val in data.values():
                if isinstance(val, list):
                    schemes = val
                    break
        # If no list found, treat dict itself as a single item
        if schemes is None:
            schemes = [data]
    else:
        schemes = []

    return [s for s in schemes if isinstance(s, dict)]

def get_scheme_name(s: Dict[str, Any]) -> str:
    """Extract scheme name/title generically across varied field names."""
    for key in ["name", "title", "scheme_name", "scheme_title", "schemeName", "schemeTitle", "id"]:
        if key in s and s[key]:
            return str(s[key]).strip()
    # Check case-insensitively for keys containing name or title
    for k, v in s.items():
        if any(term in k.lower() for term in ["name", "title"]) and v:
            return str(v).strip()
    # Fallback to first non-empty string value
    for v in s.values():
        if isinstance(v, str) and 2 < len(v) < 120:
            return v.strip()
    return "Government Scheme"

def get_scheme_url(s: Dict[str, Any]) -> str:
    """Extract scheme source URL generically across varied field names."""
    for key in ["application_url", "source_url", "url", "link", "source", "website", "web_url", "portal_url", "portal", "apply_url"]:
        if key in s and s[key] and str(s[key]).strip().lower().startswith(("http://", "https://")):
            return str(s[key]).strip()
    # Search all values for http/https links
    for v in s.values():
        if isinstance(v, str) and v.strip().lower().startswith(("http://", "https://")):
            return v.strip()
    return ""

def scheme_to_search_text(s: Dict[str, Any]) -> str:
    """Flatten all scheme fields into a single text blob for TF-IDF search indexing."""
    parts = []
    for k, v in s.items():
        if isinstance(v, (str, int, float)):
            parts.append(f"{k} {v}")
        elif isinstance(v, list):
            items = [str(item) for item in v if isinstance(item, (str, int, float))]
            parts.append(f"{k} {' '.join(items)}")
        elif isinstance(v, dict):
            sub = [f"{sk} {sv}" for sk, sv in v.items() if isinstance(sv, (str, int, float))]
            parts.append(f"{k} {' '.join(sub)}")
    return " ".join(parts).strip()

def scheme_to_context(s: Dict[str, Any]) -> str:
    """Format any scheme generically into clear text for LLM grounding context."""
    name = get_scheme_name(s)
    lines = [f"SCHEME: {name}"]
    for k, v in s.items():
        label = k.replace("_", " ").strip().title()
        if isinstance(v, list):
            lines.append(f"{label}: {', '.join(str(item) for item in v)}")
        elif isinstance(v, dict):
            sub = "; ".join(f"{sk}: {sv}" for sk, sv in v.items())
            lines.append(f"{label}: {sub}")
        else:
            lines.append(f"{label}: {v}")
    return "\n".join(lines)

# ---------- Search Index ----------
SCHEMES = load_schemes_data()
corpus = [scheme_to_search_text(s) for s in SCHEMES]

if corpus and any(len(c.strip()) > 0 for c in corpus):
    vectorizer = TfidfVectorizer(stop_words="english", token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform(corpus)
else:
    vectorizer = None
    matrix = None

def find_schemes(english_query: str, k: int = 3) -> List[Dict[str, Any]]:
    """Retrieve top k matching schemes using cosine similarity with adaptive thresholding."""
    if vectorizer is None or matrix is None or not SCHEMES or not english_query:
        return []
    try:
        q_vec = vectorizer.transform([english_query])
        scores = cosine_similarity(q_vec, matrix)[0]
        best_indices = scores.argsort()[::-1]
        top_score = scores[best_indices[0]]
        if top_score < 0.05:
            return []
        # Dynamic threshold: must be at least 0.05 and within 40% of the top match
        threshold = max(0.05, top_score * 0.4)
        return [SCHEMES[i] for i in best_indices if scores[i] >= threshold][:k]
    except Exception as e:
        print(f"Error matching schemes: {e}")
        return []

# ---------- AI Pipeline ----------
def chat(client: Groq, system: str, user: str) -> str:
    """Call Groq LLaMA chat completion."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()

def translate_to_english(client: Groq, text: str, lang: str) -> str:
    """Translate non-English query to English for accurate knowledge retrieval."""
    if lang == "en":
        return text
    system_prompt = (
        "Translate the user query into concise English for searching a government scheme database. "
        "If it is already in English, output it as is. Output ONLY the English translation with no extra commentary."
    )
    try:
        translated = chat(client, system_prompt, text)
        return translated or text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def answer_question(question: str, lang: str = "en") -> Dict[str, Any]:
    """
    Main answering pipeline:
    1. Validate/normalize language
    2. Translate query to English if necessary
    3. Retrieve relevant schemes via TF-IDF
    4. Synthesize simple voice-friendly response grounded in context
    """
    clean_lang = (lang or "en").lower().strip()[:2]
    target_lang = clean_lang if clean_lang in LANG_NAMES else "en"

    if not question or not question.strip():
        return {
            "question": question,
            "answer": FALLBACK[target_lang],
            "sources": [],
            "found": False,
        }

    client = get_groq_client()

    # 1. Translate question to English for retrieval
    english_q = translate_to_english(client, question.strip(), target_lang)

    # 2. Retrieve candidate schemes
    matches = find_schemes(english_q)
    if not matches:
        return {
            "question": question,
            "answer": FALLBACK[target_lang],
            "sources": [],
            "found": False,
        }

    # 3. Build context and prompt LLM
    context = "\n\n".join(scheme_to_context(s) for s in matches)
    system_prompt = (
        "You are Bolo, a voice assistant for Indian government services. "
        "Answer ONLY using the provided Context. "
        f"Reply in {LANG_NAMES[target_lang]} using very simple, clear words in maximum 3 short sentences. "
        "Do NOT use markdown symbols, asterisks, or bullet points because this will be spoken aloud to citizens. "
        "If the Context does not contain the answer, reply with exactly: NO_ANSWER"
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {english_q}"

    reply = chat(client, system_prompt, user_prompt)

    if "NO_ANSWER" in reply or not reply:
        return {
            "question": question,
            "answer": FALLBACK[target_lang],
            "sources": [],
            "found": False,
        }

    sources = [{"name": get_scheme_name(s), "url": get_scheme_url(s)} for s in matches]

    return {
        "question": question,
        "answer": reply,
        "sources": sources,
        "found": True,
    }

# ---------- FastAPI Server ----------
app = FastAPI(title="Bolo", description="Voice Assistant for Indian Government Services")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextQuestion(BaseModel):
    question: str
    lang: str = "en"

@app.get("/health")
def health():
    """Health check endpoint: returns status and count of loaded schemes."""
    return {"status": "ok", "schemes_loaded": len(SCHEMES)}

@app.post("/ask-text")
def ask_text(body: TextQuestion):
    """Text query endpoint: accepts JSON question and language."""
    return answer_question(body.question, body.lang)

@app.post("/ask-voice")
async def ask_voice(audio: UploadFile = File(...), lang: str = Form("en")):
    """Voice query endpoint: transcribes audio with Whisper, then runs answer pipeline."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio recording received.")

    client = get_groq_client()

    clean_lang = (lang or "en").lower().strip()[:2]
    whisper_lang = clean_lang if clean_lang in LANG_NAMES else "en"

    # Ensure Whisper receives a supported file extension
    orig_filename = (audio.filename or "").lower()
    content_type = (audio.content_type or "").lower()

    if orig_filename.endswith((".webm", ".mp4", ".m4a", ".wav", ".ogg", ".mp3")):
        filename = audio.filename
    elif "mp4" in content_type or "m4a" in content_type:
        filename = "recording.mp4"
    elif "wav" in content_type:
        filename = "recording.wav"
    elif "ogg" in content_type:
        filename = "recording.ogg"
    elif "mp3" in content_type:
        filename = "recording.mp3"
    else:
        filename = "recording.webm"

    try:
        transcription = client.audio.transcriptions.create(
            file=(filename, data),
            model=STT_MODEL,
            language=whisper_lang,
        )
        transcribed_text = (transcription.text or "").strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech transcription failed: {str(e)}")

    if not transcribed_text:
        return {
            "question": "",
            "answer": FALLBACK.get(whisper_lang, FALLBACK["en"]),
            "sources": [],
            "found": False,
        }

    return answer_question(transcribed_text, whisper_lang)

# Mount static frontend if available, else root returns health
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"status": "ok", "schemes_loaded": len(SCHEMES)}
