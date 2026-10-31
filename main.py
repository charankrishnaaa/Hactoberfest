"""Bolo backend: question in -> short answer + sources out."""
import os
import re
import json
import math
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from groq import Groq

# ---------- settings ----------
client = Groq(api_key=os.environ["GROQ_API_KEY"])
LLM_MODEL = "openai/gpt-oss-120b"   # open-weight; if Groq says not found, check console.groq.com/docs/models
STT_MODEL = "whisper-large-v3"       # speech-to-text
LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu"}

# TODO: replace with a helpline you have verified on an official site
HELPLINE = "1800-XXX-XXXX"
FALLBACK = {
    "en": f"Sorry, I don't have a reliable answer. Please call the helpline {HELPLINE} or visit your nearest CSC / Mee Seva centre.",
    "hi": f"माफ़ कीजिए, मेरे पास इसका पक्का जवाब नहीं है। कृपया हेल्पलाइन {HELPLINE} पर कॉल करें या नज़दीकी CSC केंद्र जाएँ।",
    "te": f"క్షమించండి, దీనికి నా దగ్గర ఖచ్చితమైన సమాధానం లేదు. దయచేసి హెల్ప్‌లైన్ {HELPLINE} కు కాల్ చేయండి లేదా దగ్గరలోని CSC / మీ సేవ కేంద్రానికి వెళ్లండి.",
}

# ---------- load the JSON data ONCE when the server starts ----------
_raw = json.loads(Path(__file__).with_name("schemes.json").read_text(encoding="utf-8"))
# works if the file is a list [...] or an object like {"schemes": [...]}
SCHEMES = _raw if isinstance(_raw, list) else next(v for v in _raw.values() if isinstance(v, list))

def flat(v):
    """Turn any value (text, list, nested object) into plain text."""
    if isinstance(v, dict):
        return " ".join(flat(x) for x in v.values())
    if isinstance(v, list):
        return " ".join(flat(x) for x in v)
    return str(v)

def scheme_text(s):
    return flat(s)

def scheme_name(s):
    return s.get("name") or s.get("title") or s.get("scheme_name") or "Scheme"

def scheme_url(s):
    return s.get("source_url") or s.get("application_url") or s.get("url") or s.get("link") or ""

# ---------- search: small TF-IDF written in plain Python (no heavy libraries) ----------
STOP = set("a an the of for to in on and or is are was be can i me my we you your how what which who "
           "do does get gets with from at by this that it as under any all".split())

def tokens(text):
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if len(w) < 2 or w in STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]                      # pensions -> pension
        out.append(w)
    return out

DOCS = [Counter(tokens(scheme_text(s))) for s in SCHEMES]
N = len(DOCS)
DF = Counter(w for d in DOCS for w in d)
IDF = {w: math.log((1 + N) / (1 + df)) + 1 for w, df in DF.items()}

def to_vec(counter):
    v = {w: (1 + math.log(c)) * IDF[w] for w, c in counter.items() if w in IDF}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {w: x / norm for w, x in v.items()}

DOC_VECS = [to_vec(d) for d in DOCS]

def find_schemes(english_question, k=3):
    """Return the k schemes whose text best matches the question."""
    q = to_vec(Counter(tokens(english_question)))
    scores = [sum(x * dv.get(w, 0.0) for w, x in q.items()) for dv in DOC_VECS]
    best = sorted(range(N), key=lambda i: scores[i], reverse=True)[:k]
    return [SCHEMES[i] for i in best if scores[i] > 0.05]

# How the answer should SOUND in each language (this removes the stiff, translated feel)
STYLE = {
    "en": "Use plain, friendly English that a village help-desk volunteer would use.",
    "hi": ("Use simple everyday spoken Hindi (bolchal ki Hindi), like a helpful neighbour talking to an elder. "
           "Avoid heavy Sanskrit words. Keep words people say daily in English as they are, written in Devanagari "
           "(Aadhaar card, ration card, bank account, form, online, CSC)."),
    "te": ("Use simple everyday SPOKEN Telugu (vyavaharika Telugu), the way a friendly village helper in Telangana or "
           "Andhra talks to an elder. Do NOT use bookish, formal or Sanskritized Telugu, and do NOT translate word by "
           "word from English; say it the natural way. Use short sentences and address the person politely as 'meeru' "
           "(మీరు). Keep words people commonly say in English, written in Telugu script: ఆధార్ కార్డు, రేషన్ కార్డు, "
           "బ్యాంక్ అకౌంట్, ఫారం, ఆన్‌లైన్, మీ సేవ, CSC. Keep scheme names as they are. Say money like '5 లక్షల రూపాయలు'. "
           "Tone example only (never copy its content): 'ఈ కార్డు కావాలంటే మీ ఆధార్ కార్డు, రేషన్ కార్డు తీసుకుని "
           "దగ్గరలోని మీ సేవ సెంటర్‌కి వెళ్లండి.'"),
}

# ---------- AI helpers ----------
def chat(system, user, temperature=0):
    r = client.chat.completions.create(
        model=LLM_MODEL, temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (r.choices[0].message.content or "").strip()

def _answer(question, lang):
    lang = lang if lang in LANG_NAMES else "en"
    # 1. our data is in English, so translate the question to English for searching
    english_q = question if lang == "en" else chat("Translate to English. Output only the translation.", question)
    # 2. find matching schemes in schemes.json
    matches = find_schemes(english_q)
    if not matches:
        return {"question": question, "answer": FALLBACK[lang], "sources": [], "found": False}
    # 3. build context and ask the AI to answer ONLY from it
    context = "\n\n".join(
        f"SCHEME: {scheme_name(s)}\n{json.dumps(s, ensure_ascii=False)[:3000]}" for s in matches
    )
    system = (
        "You are Bolo, a helper for Indian government schemes. Answer ONLY using the context given. "
        f"Reply in {LANG_NAMES[lang]}. {STYLE[lang]} "
        "Maximum 3 short sentences. Do not use bullet points, markdown or symbols like ** or #. "
        "If the context does not contain the answer, reply with exactly: NO_ANSWER"
    )
    reply = chat(system, f"Context:\n{context}\n\nQuestion: {english_q}", temperature=0.3)
    if not reply or "NO_ANSWER" in reply:
        return {"question": question, "answer": FALLBACK[lang], "sources": [], "found": False}
    sources = [{"name": scheme_name(s), "url": scheme_url(s)} for s in matches]
    return {"question": question, "answer": reply, "sources": sources, "found": True}

# ---------- language auto-detection ----------
def detect_lang_from_text(text):
    """Telugu letters -> te, Devanagari letters -> hi, otherwise English."""
    te = sum(1 for c in text if "\u0C00" <= c <= "\u0C7F")
    hi = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    if te and te >= hi:
        return "te"
    if hi:
        return "hi"
    return "en"

def answer_question(question, lang):
    """lang can be en / hi / te, or 'auto' to detect it from the question text."""
    if lang not in LANG_NAMES:
        lang = detect_lang_from_text(question)
    result = _answer(question, lang)
    result["lang"] = lang          # frontend uses this to pick the voice
    return result

# Whisper returns full language names. Map them to our 3 languages.
WHISPER_TO_LANG = {"english": "en", "hindi": "hi", "telugu": "te"}
# Whisper often mislabels Hindi/Telugu speech as a neighbouring language. Map those too.
NEARBY = {"urdu": "hi", "marathi": "hi", "punjabi": "hi", "nepali": "hi", "bengali": "hi",
          "kannada": "te", "tamil": "te", "malayalam": "te"}

def transcribe(data, filename, lang):
    """Speech to text. Returns (text, language_code). lang='auto' -> detect the language."""
    if lang in LANG_NAMES:
        r = client.audio.transcriptions.create(file=(filename, data), model=STT_MODEL, language=lang)
        return r.text, lang
    r = client.audio.transcriptions.create(
        file=(filename, data), model=STT_MODEL, response_format="verbose_json")
    detected = (getattr(r, "language", "") or "").lower()
    if detected in WHISPER_TO_LANG:
        return r.text, WHISPER_TO_LANG[detected]
    if detected in NEARBY:      # re-run, forcing the most likely Indian language
        code = NEARBY[detected]
        r2 = client.audio.transcriptions.create(file=(filename, data), model=STT_MODEL, language=code)
        return r2.text, code
    return r.text, detect_lang_from_text(r.text)

# ---------- the web server ----------
app = FastAPI(title="Bolo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TextQuestion(BaseModel):
    question: str
    lang: str = "auto"

STATIC = next((p for p in (Path(__file__).with_name("public"), Path(__file__).with_name("static")) if p.exists()), None)

if STATIC is None:
    # no "static" folder -> serve the single index.html next to main.py
    @app.get("/")
    def home():
        return FileResponse(Path(__file__).with_name("index.html"))

@app.get("/health")
def health():
    return {"status": "Bolo is running", "schemes_loaded": len(SCHEMES)}

def safe_fallback(question, lang, why):
    """Never show a crash to the user: return the helpline message instead."""
    print("ERROR:", why)                       # the real reason shows in the server terminal
    code = lang if lang in LANG_NAMES else detect_lang_from_text(question or "")
    return {"question": question or "", "answer": FALLBACK[code], "sources": [],
            "found": False, "lang": code, "error": str(why)[:200]}

@app.post("/ask-text")
def ask_text(body: TextQuestion):
    if not body.question.strip():
        return safe_fallback("", body.lang, "empty question")
    try:
        return answer_question(body.question, body.lang)
    except Exception as e:
        return safe_fallback(body.question, body.lang, e)

@app.post("/ask-voice")
async def ask_voice(audio: UploadFile = File(...), lang: str = Form("auto")):
    data = await audio.read()
    if not data:
        return safe_fallback("", lang, "empty audio")
    try:
        text, code = transcribe(data, audio.filename or "audio.webm", lang)
        if not text.strip():
            return safe_fallback("", code, "no speech heard")
        return answer_question(text, code)
    except Exception as e:
        return safe_fallback("", lang, e)

# ---------- serve a multi-file frontend ----------
# Put ALL your frontend files (html, css, js, images) inside a folder named "static".
# Must stay at the bottom of this file so the API routes above are matched first.
if STATIC is not None:
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
