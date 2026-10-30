import os
import re
import json
import math
import logging
from typing import List, Dict, Any, Optional
from collections import Counter

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bolo_backend")

# ==================== CONSTANTS & CONFIGURATION ====================
# Models (open-source / open-weight models via Groq)
STT_MODEL = "whisper-large-v3"
LLM_MODEL = "openai/gpt-oss-120b"

# Helpline number (TODO: replace with a verified national/state government helpline)
HELPLINE = "1800-XXX-XXXX"

# Language fallback messages when information is unknown or not found
UNKNOWN_MESSAGES = {
    "en": f"I am not completely sure about this from the official records. Please visit your nearest CSC or Mee Seva centre, or call the helpline at {HELPLINE}.",
    "hi": f"मुझे आधिकारिक सरकारी रिकॉर्ड में इसकी पूरी जानकारी नहीं मिली। कृपया अपने नज़दीकी सीएससी (CSC) या जन सेवा केंद्र जाएं, या {HELPLINE} हेल्पलाइन पर संपर्क करें।",
    "te": f"ఈ పథకం గురించి నాకు అధికారిక వివరాలు పూర్తిగా దొరకలేదు. దయచేసి మీ దగ్గరలోని మీ సేవ లేదా CSC కేంద్రానికి వెళ్లండి, లేదా {HELPLINE} హెల్ప్‌లైన్‌కు కాల్ చేయండి."
}

# The 12 standard categories
CATEGORIES_LIST = [
    "Farmers",
    "Health",
    "Women & Child",
    "Students",
    "Pension & Seniors",
    "Housing",
    "Jobs & Skills",
    "Loans & Business",
    "Insurance",
    "Disability",
    "Village Development",
    "Other"
]

# Stopwords for pure-Python TF-IDF
STOPWORDS = set(
    "a about above after again against all am an and any are as at be because been before being below "
    "between both but by can did do does doing don down during each few for from further had has have "
    "having he her here hers herself him himself his how i if in into is it its itself just me more "
    "most my myself no nor not now of off on once only or other our ours ourselves out over own same "
    "she should so some such than that the their theirs them themselves then there these they this those "
    "through to too under until up very was we were what when where which while who whom why with you your "
    "yours yourself yourselves".split()
)

# Load GROQ API Key from environment or local .env file
def load_env_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        # Check backend/.env or root .env
        for env_path in [".env", "backend/.env", "../.env"]:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("GROQ_API_KEY="):
                                val = line.split("=", 1)[1].strip().strip("\"'")
                                if val:
                                    os.environ["GROQ_API_KEY"] = val
                                    return val
                except Exception as e:
                    logger.warning(f"Failed to read {env_path}: {e}")
    return os.environ.get("GROQ_API_KEY", "").strip()

GROQ_API_KEY = load_env_key()

# ==================== SCHEMES DATA & INDEXING ====================
schemes_data: List[Dict[str, Any]] = []
schemes_by_id: Dict[str, Dict[str, Any]] = {}
category_counts: Dict[str, int] = {c: 0 for c in CATEGORIES_LIST}

# TF-IDF Index structures
doc_vectors: List[Dict[str, float]] = []
doc_norms: List[float] = []
idf_dict: Dict[str, float] = {}

def stem_token(word: str) -> str:
    """Simple plural and suffix stemming in pure Python."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and (word.endswith("sses") or word.endswith("shes") or word.endswith("ches") or word.endswith("xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word

def tokenize(text: str) -> List[str]:
    """Lowercase a-z0-9 tokenizer with stopword removal and stemming."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [stem_token(w) for w in tokens if w not in STOPWORDS and len(w) > 1]

def get_first_sentence(text: str) -> str:
    """Extracts the first sentence from a description."""
    if not text:
        return ""
    parts = re.split(r"\.\s+", text.strip())
    if parts:
        s = parts[0].strip()
        if not s.endswith("."):
            s += "."
        return s
    return text.strip()

def derive_category(scheme: Dict[str, Any]) -> str:
    """Derives one of the 12 categories based on keywords in text."""
    text = (
        f"{scheme.get('scheme_name', '')} "
        f"{scheme.get('scheme_description', '')} "
        f"{scheme.get('eligibility', '')} "
        f"{scheme.get('benefits_money', '')}"
    ).lower()

    if any(k in text for k in ["divyang", "disability", "disabled", "assistive devices", "impairment", "prosthetic"]):
        return "Disability"
    if any(k in text for k in ["pension", "senior citizen", "70 years", "old age", "elderly", "vay vandana", "atal pension", "pmvvy"]):
        return "Pension & Seniors"
    if any(k in text for k in ["scholarship", "student", "fellowship", "tuition", "school", "education", "college", "vidyanjali"]):
        return "Students"
    if any(k in text for k in ["awas yojana", "housing", "pucca house", "shelter", "pmay"]):
        return "Housing"
    if any(k in text for k in ["maternal", "pregnant", "lactating", "girl child", "sukanya", "matru", "janani", "mahila", "women", "poshan", "beti bachao", "vatsalya"]):
        return "Women & Child"
    if any(k in text for k in ["farmer", "kisan", "krishi", "crop", "soil", "agriculture", "irrigation", "livestock", "dairy", "fisheries", "pm-kisan", "pmksy", "fpo"]):
        return "Farmers"
    if any(k in text for k in ["insurance", "bima", "jeevan jyoti", "suraksha bima", "accidental death", "fasal bima"]):
        return "Insurance"
    if any(k in text for k in ["health", "hospital", "medical", "medicine", "janaushadhi", "treatment", "disease", "arogya", "tele-manas", "ayushman"]):
        return "Health"
    if any(k in text for k in ["loan", "credit", "business", "entrepreneur", "startup", "mudra", "msme", "svanidhi", "vendor", "stand-up"]):
        return "Loans & Business"
    if any(k in text for k in ["skill", "employment", "job", "apprentice", "training", "kaushal", "rozgar", "mgnrega", "livelihood", "unemployed", "pmkvy"]):
        return "Jobs & Skills"
    if any(k in text for k in ["gram", "panchayat", "village", "sanitation", "swachh", "jal jeevan", "pmgsy", "rural road", "electrification", "saubhagya", "solar rooftop", "pm-surya", "ujala", "lpg", "ujjwala"]):
        return "Village Development"
    return "Other"

def load_and_index_schemes():
    """Loads schemes.json from disk and constructs the in-memory TF-IDF index."""
    global schemes_data, schemes_by_id, category_counts, doc_vectors, doc_norms, idf_dict
    
    # Try finding schemes.json in current directory, backend/, or parent
    target_path = None
    for p in ["schemes.json", "backend/schemes.json", "../schemes.json"]:
        if os.path.exists(p):
            target_path = p
            break
            
    if not target_path:
        logger.error("Could not find schemes.json!")
        return

    logger.info(f"Loading schemes from {target_path}...")
    with open(target_path, "r", encoding="utf-8") as f:
        schemes_data = json.load(f)

    category_counts = {c: 0 for c in CATEGORIES_LIST}
    schemes_by_id = {}
    doc_tokens_list = []
    df_counter = Counter()

    for s in schemes_data:
        s_id = s.get("id")
        schemes_by_id[s_id] = s
        cat = derive_category(s)
        s["_category"] = cat  # Keep in memory only, never written to file
        category_counts[cat] = category_counts.get(cat, 0) + 1

        # Combine text fields for indexing, repeating name for extra relevance
        full_text = (
            f"{s.get('scheme_name', '')} {s.get('scheme_name', '')} {s.get('scheme_name', '')} "
            f"{s.get('scheme_description', '')} "
            f"{s.get('eligibility', '')} "
            f"{s.get('benefits_money', '')} "
            f"{s.get('age_limit', '')} "
            f"{s.get('income_limit', '')} "
            f"{' '.join(s.get('documents', []))} "
            f"{s.get('application_process', '')} "
            f"{cat}"
        )
        tokens = tokenize(full_text)
        doc_tokens_list.append(tokens)
        for t in set(tokens):
            df_counter[t] += 1

    N = len(schemes_data)
    idf_dict = {t: math.log(1.0 + (N / (1.0 + freq))) + 1.0 for t, freq in df_counter.items()}

    doc_vectors = []
    doc_norms = []
    for tokens in doc_tokens_list:
        tf_counts = Counter(tokens)
        vec = {}
        norm_sq = 0.0
        for t, c in tf_counts.items():
            w = (1.0 + math.log(c)) * idf_dict.get(t, 1.0)
            vec[t] = w
            norm_sq += w * w
        doc_vectors.append(vec)
        doc_norms.append(math.sqrt(norm_sq))

    logger.info(f"Successfully loaded {len(schemes_data)} schemes. Indexed {len(idf_dict)} unique terms.")

# Load immediately on module import
load_and_index_schemes()

def search_schemes(query: str, top_k: int = 4, min_score: float = 0.08) -> List[Dict[str, Any]]:
    """Pure Python TF-IDF search over schemes."""
    if not query or not schemes_data:
        return []
        
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    q_tf = Counter(q_tokens)
    q_vec = {}
    q_norm_sq = 0.0
    for t, c in q_tf.items():
        if t in idf_dict:
            w = (1.0 + math.log(c)) * idf_dict[t]
            q_vec[t] = w
            q_norm_sq += w * w

    if q_norm_sq == 0:
        return []

    q_norm = math.sqrt(q_norm_sq)
    scores = []
    for idx, d_vec in enumerate(doc_vectors):
        dot = sum(w * d_vec.get(t, 0.0) for t, w in q_vec.items())
        score = dot / (q_norm * doc_norms[idx]) if doc_norms[idx] > 0 else 0.0
        if score >= min_score:
            scores.append((score, schemes_data[idx]))

    scores.sort(key=lambda x: -x[0])
    return [item for sc, item in scores[:top_k]]

# ==================== LANGUAGE & SCRIPT HELPERS ====================
def detect_script_language(text: str) -> str:
    """Detect language from Unicode script if not determinable from whisper."""
    telugu_count = sum(1 for c in text if 0x0C00 <= ord(c) <= 0x0C7F)
    devanagari_count = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    
    if telugu_count > 0:
        return "te"
    if devanagari_count > 0:
        return "hi"
    return "en"

# ==================== GROQ CLIENT & MODEL FALLBACK ====================
def get_groq_client() -> Optional[Groq]:
    key = load_env_key()
    if not key:
        return None
    try:
        return Groq(api_key=key)
    except Exception as e:
        logger.error(f"Failed to create Groq client: {e}")
        return None

def verify_and_get_llm_model(client: Groq) -> str:
    """Verifies that the LLM is available and falls back to an open-weight model if rejected."""
    global LLM_MODEL
    try:
        models = client.models.list()
        avail_ids = [m.id for m in models.data]
        if LLM_MODEL in avail_ids:
            return LLM_MODEL
            
        # Fallback list of open-source / open-weight models on Groq
        for candidate in ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"]:
            if candidate in avail_ids:
                LLM_MODEL = candidate
                logger.info(f"Switched LLM_MODEL to active open model: {LLM_MODEL}")
                return LLM_MODEL
                
        # Last resort: pick any model not containing closed tags
        for m_id in avail_ids:
            low = m_id.lower()
            if not any(tag in low for tag in ["gpt-4", "gpt-3.5", "claude", "gemini"]):
                LLM_MODEL = m_id
                logger.info(f"Selected open model from list: {LLM_MODEL}")
                return LLM_MODEL
    except Exception as e:
        logger.warning(f"Could not verify models list: {e}")
    return LLM_MODEL

# ==================== CORE CONVERSATION ENGINE ====================
def build_search_query(client: Groq, model: str, question: str, history: List[Dict[str, Any]]) -> str:
    """Uses the LLM at temperature 0 to turn conversation + question into a concise English search query."""
    try:
        hist_lines = []
        for h in history[-4:]:
            role = "User" if h.get("role") == "user" else "Bolo"
            txt = h.get("text", "")
            hist_lines.append(f"{role}: {txt}")
        history_str = "\n".join(hist_lines) if hist_lines else "None"

        prompt = (
            "You are a search query generator for an Indian government welfare schemes database.\n"
            "Given the conversation history and the user's latest query, write ONE concise English search query "
            "(2 to 6 keywords) targeting the specific scheme, beneficiary group, or service.\n"
            "If the user is answering a question (like 'yes', 'no', '45 years', 'farmer'), combine it with the earlier topic.\n"
            "Output ONLY the plain search keywords. Do NOT output punctuation, quotes, or explanations.\n\n"
            f"History:\n{history_str}\n\n"
            f"Latest User Query: {question}\n\n"
            "Search Query:"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        content = resp.choices[0].message.content or ""
        clean_q = re.sub(r'["\n\r]', ' ', content).strip()
        logger.info(f"Generated search query: '{clean_q}' from input: '{question}'")
        return clean_q if clean_q else question
    except Exception as e:
        logger.warning(f"Error in build_search_query: {e}")
        return question

def process_bolo_conversation(question: str, lang: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Core eligibility helper and scheme answering logic."""
    client = get_groq_client()
    if not client:
        logger.error("GROQ_API_KEY is not set!")
        err_msg = UNKNOWN_MESSAGES.get(lang, UNKNOWN_MESSAGES["en"])
        return {
            "transcript": question,
            "lang": lang,
            "type": "unknown",
            "text": err_msg,
            "options": [],
            "sources": [],
            "found": False,
            "error": "GROQ_API_KEY is not configured on the server."
        }

    active_model = verify_and_get_llm_model(client)

    # 1. Generate standalone English query
    search_q = build_search_query(client, active_model, question, history)

    # 2. Retrieve schemes
    retrieved = search_schemes(search_q, top_k=4, min_score=0.07)
    logger.info(f"Retrieved {len(retrieved)} schemes for query '{search_q}'")

    # If nothing even remotely matched, return unknown immediately
    if not retrieved:
        logger.info("No schemes retrieved above threshold.")
        return {
            "transcript": question,
            "lang": lang,
            "type": "unknown",
            "text": UNKNOWN_MESSAGES.get(lang, UNKNOWN_MESSAGES["en"]),
            "options": [],
            "sources": [],
            "found": False
        }

    # Format scheme context
    context_blocks = []
    for s in retrieved:
        block = (
            f"Scheme Name: {s.get('scheme_name')}\n"
            f"Category: {s.get('_category', 'Other')}\n"
            f"Description: {s.get('scheme_description')}\n"
            f"Eligibility: {s.get('eligibility')}\n"
            f"Benefits: {s.get('benefits_money')}\n"
            f"Age Limit: {s.get('age_limit')}\n"
            f"Income Limit: {s.get('income_limit')}\n"
            f"Documents Required: {', '.join(s.get('documents', []))}\n"
            f"How to Apply: {s.get('application_process')}\n"
            f"Official Link: {s.get('application_url')}"
        )
        context_blocks.append(block)
    schemes_context = "\n---\n".join(context_blocks)

    # Count follow-up turns already asked by Bolo
    questions_asked = sum(
        1 for h in history if h.get("role") == "bolo" and h.get("kind") == "question"
    )

    # Language style instructions
    if lang == "hi":
        style_inst = (
            "Language: Hindi (हिन्दी).\n"
            "Tone: Simple everyday spoken Hindi (bolchal), absolutely NO heavy or archaic Sanskrit words.\n"
            "Keep common terms naturally: आधार कार्ड, राशन कार्ड, बैंक खाता/अकाउंट, फॉर्म, ऑनलाइन, सीएससी (CSC).\n"
            "Be warm, respectful, like a kind village helper (volunteers at Gram Panchayat)."
        )
    elif lang == "te":
        style_inst = (
            "Language: Telugu (తెలుగు).\n"
            "Tone: Simple everyday SPOKEN Telugu (వ్యవహారిక భాష), the way a kind village helper in Telangana/Andhra talks to an elder.\n"
            "NOT bookish or formal translation. Use short simple sentences. Use polite 'మీరు'.\n"
            "Keep words people say in English written in Telugu script (ఆధార్ కార్డు, రేషన్ కార్డు, బ్యాంక్ అకౌంట్, ఫారం, ఆన్లైన్, మీ సేవ, CSC).\n"
            "Express money naturally like '5 లక్షల రూపాయలు' or '6 వేల రూపాయలు'."
        )
    else:
        style_inst = (
            "Language: English.\n"
            "Tone: Plain, friendly, warm, like a helpful village volunteer. Avoid bureaucratic jargon."
        )

    # Format history
    hist_text = []
    for h in history[-6:]:
        r = "User" if h.get("role") == "user" else "Bolo"
        hist_text.append(f"{r}: {h.get('text', '')}")
    history_str = "\n".join(hist_text) if hist_text else "None"

    system_prompt = (
        "You are Bolo, a kind, patient village help-desk volunteer helping rural and semi-urban Indian citizens understand government schemes.\n"
        "You speak like a caring helper, NOT a robot or plain chatbot.\n\n"
        f"{style_inst}\n\n"
        "CRITICAL RULES:\n"
        "1. GROUNDING: Answer ONLY from the retrieved scheme data below. Maximum 3 short sentences. Never invent amounts, dates or rules.\n"
        "2. NO MARKDOWN: Never use asterisks (*), hashtags (#), bullet points, or symbols.\n"
        "3. ALWAYS mention the scheme name at least once.\n"
        "4. ELIGIBILITY HELPER:\n"
        f"   - Number of follow-up questions already asked: {questions_asked} of 3 maximum.\n"
        "   - If the user's inquiry is about eligibility ('can I get', 'am I eligible', 'who can apply') AND crucial facts (e.g. land ownership, age, income, gender, student status) are missing from the history:\n"
        f"     * If questions_asked < 3: Set action to 'ask', ask ONE short follow-up question, and provide 2-3 short tappable options (e.g. ['Yes', 'No'] or ['అవును', 'కాదు'] or ['हाँ', 'नहीं']).\n"
        "     * If questions_asked >= 3: Do NOT ask any more questions. Set action to 'answer' and make a final determination based on what the user said.\n"
        "   - If the user asks about documents, application process, benefits, or what the scheme is: Set action to 'answer' directly without follow-up questions.\n"
        "   - Interpret short user inputs like 'yes', 'no', '2 acres', or numbers in the context of the prior question.\n"
        "5. UNKNOWN TOPIC:\n"
        "   - If the user's question is NOT about Indian government welfare schemes (e.g. passport, cricket, general chat, movies), or if the retrieved schemes do NOT contain the answer: Set action to 'unknown'.\n\n"
        "You MUST respond with a strict JSON object with this exact structure:\n"
        "{\n"
        '  "action": "answer" | "ask" | "unknown",\n'
        '  "scheme_name": "Name of primary scheme or null",\n'
        '  "text": "Your spoken reply in the target language (max 3 short sentences)",\n'
        '  "options": ["Option 1", "Option 2"] // only for action "ask", otherwise []\n'
        "}"
    )

    user_prompt = (
        f"RETRIEVED SCHEMES CONTEXT:\n{schemes_context}\n\n"
        f"CONVERSATION HISTORY:\n{history_str}\n\n"
        f"LATEST USER QUERY:\n{question}\n\n"
        "JSON Response:"
    )

    try:
        completion = client.chat.completions.create(
            model=active_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        raw_msg = completion.choices[0].message.content or ""
        logger.info(f"LLM raw response: {raw_msg[:120]}...")

        # Parse JSON robustly
        parsed = None
        clean_text = raw_msg.strip()
        # Remove code fences if present
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)
        
        try:
            parsed = json.loads(clean_text)
        except Exception:
            # Fallback: regex search for JSON block
            m = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    pass

        if not parsed or not isinstance(parsed, dict):
            # Treat raw text as an answer if parsing failed
            action = "answer" if clean_text else "unknown"
            reply_text = clean_text if clean_text else UNKNOWN_MESSAGES.get(lang, UNKNOWN_MESSAGES["en"])
            options = []
            scheme_name = retrieved[0].get("scheme_name") if retrieved else None
        else:
            action = parsed.get("action", "answer")
            reply_text = parsed.get("text", "").strip()
            options = parsed.get("options", [])
            scheme_name = parsed.get("scheme_name")

        # Strip any accidental markdown symbols from reply_text
        reply_text = re.sub(r"[*#_`]", "", reply_text).strip()

        if action == "unknown" or not reply_text:
            return {
                "transcript": question,
                "lang": lang,
                "type": "unknown",
                "text": UNKNOWN_MESSAGES.get(lang, UNKNOWN_MESSAGES["en"]),
                "options": [],
                "sources": [],
                "found": False
            }

        # Build sources list
        sources = []
        if action in ("answer", "ask"):
            # If scheme_name matched one of the retrieved, use it; else include top 1-2 retrieved
            matched = False
            if scheme_name:
                for s in retrieved:
                    if s.get("scheme_name", "").lower() in scheme_name.lower() or scheme_name.lower() in s.get("scheme_name", "").lower():
                        sources.append({
                            "id": s.get("id"),
                            "name": s.get("scheme_name"),
                            "url": s.get("application_url")
                        })
                        matched = True
                        break
            if not matched and retrieved:
                sources.append({
                    "id": retrieved[0].get("id"),
                    "name": retrieved[0].get("scheme_name"),
                    "url": retrieved[0].get("application_url")
                })

        return {
            "transcript": question,
            "lang": lang,
            "type": "question" if action == "ask" else "answer",
            "text": reply_text,
            "options": options if action == "ask" else [],
            "sources": sources,
            "found": True
        }

    except Exception as e:
        logger.error(f"Error in LLM conversation: {e}", exc_info=True)
        return {
            "transcript": question,
            "lang": lang,
            "type": "unknown",
            "text": UNKNOWN_MESSAGES.get(lang, UNKNOWN_MESSAGES["en"]),
            "options": [],
            "sources": [],
            "found": False,
            "error": str(e)
        }

# ==================== FASTAPI APP ====================
app = FastAPI(title="Bolo API", description="Voice-first Government Schemes Assistant for Rural India")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskTextRequest(BaseModel):
    question: str
    lang: str = "auto"
    history: List[Dict[str, Any]] = []

@app.get("/health")
def health():
    return {
        "status": "ok",
        "schemes_loaded": len(schemes_data)
    }

@app.get("/schemes")
def list_schemes(category: Optional[str] = None, q: Optional[str] = None):
    results = []
    
    # Optional search filtering
    filtered = schemes_data
    if q and q.strip():
        search_hits = search_schemes(q.strip(), top_k=50, min_score=0.03)
        filtered = search_hits if search_hits else []

    cat_norm = category.strip().lower() if category else ""

    for s in filtered:
        s_cat = s.get("_category", "Other")
        if cat_norm and cat_norm != "all" and s_cat.lower() != cat_norm:
            continue
            
        results.append({
            "id": s.get("id"),
            "name": s.get("scheme_name"),
            "short": get_first_sentence(s.get("scheme_description", "")),
            "category": s_cat,
            "benefit": s.get("benefits_money", ""),
            "url": s.get("application_url", "")
        })

    return results

@app.get("/schemes/{scheme_id}")
def get_scheme(scheme_id: str):
    s = schemes_by_id.get(scheme_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scheme not found")
        
    return {
        "id": s.get("id"),
        "scheme_name": s.get("scheme_name"),
        "scheme_description": s.get("scheme_description"),
        "category": s.get("_category", "Other"),
        "eligibility": s.get("eligibility"),
        "benefits_money": s.get("benefits_money"),
        "age_limit": s.get("age_limit"),
        "income_limit": s.get("income_limit"),
        "documents": s.get("documents", []),
        "application_process": s.get("application_process"),
        "application_url": s.get("application_url"),
        "source_and_verification_date": s.get("source_and_verification_date")
    }

@app.get("/categories")
def list_categories():
    return [{"name": cat, "count": category_counts.get(cat, 0)} for cat in CATEGORIES_LIST]

@app.post("/ask-text")
def ask_text(req: AskTextRequest):
    try:
        raw_lang = req.lang.lower().strip()
        # Resolve language if auto
        if raw_lang == "auto" or raw_lang not in ("en", "hi", "te"):
            final_lang = detect_script_language(req.question)
        else:
            final_lang = raw_lang

        return process_bolo_conversation(req.question, final_lang, req.history)
    except Exception as e:
        logger.error(f"Top-level error in /ask-text: {e}", exc_info=True)
        return {
            "transcript": req.question,
            "lang": "en",
            "type": "unknown",
            "text": UNKNOWN_MESSAGES["en"],
            "options": [],
            "sources": [],
            "found": False,
            "error": str(e)
        }

@app.post("/ask-voice")
async def ask_voice(
    audio: UploadFile = File(...),
    lang: str = Form("auto"),
    history: str = Form("[]")
):
    try:
        # Parse history JSON string
        try:
            parsed_history = json.loads(history) if history else []
        except Exception:
            parsed_history = []

        client = get_groq_client()
        if not client:
            return {
                "transcript": "",
                "lang": "en" if lang == "auto" else lang,
                "type": "unknown",
                "text": UNKNOWN_MESSAGES["en"],
                "options": [],
                "sources": [],
                "found": False,
                "error": "GROQ_API_KEY is not configured on the server."
            }

        audio_bytes = await audio.read()
        filename = audio.filename or "recording.webm"
        file_tuple = (filename, audio_bytes)

        req_lang = lang.lower().strip()
        transcribed_text = ""
        detected_lang = req_lang

        if req_lang == "auto":
            # Call Whisper with verbose_json to detect language
            transcription = client.audio.transcriptions.create(
                file=file_tuple,
                model=STT_MODEL,
                response_format="verbose_json"
            )
            raw_detected = getattr(transcription, "language", "") or ""
            transcribed_text = getattr(transcription, "text", "") or ""
            raw_detected = raw_detected.lower()
            logger.info(f"Whisper auto-detected raw language: '{raw_detected}'")

            # Check common Whisper mislabels
            telugu_group = {"telugu", "te", "kannada", "kn", "tamil", "ta", "malayalam", "ml"}
            hindi_group = {"hindi", "hi", "urdu", "ur", "marathi", "mr", "punjabi", "pa", "nepali", "ne", "bengali", "bn"}

            if raw_detected in telugu_group and raw_detected not in ("telugu", "te"):
                logger.info(f"Remapping detected language '{raw_detected}' to Telugu ('te') and re-transcribing...")
                re_tr = client.audio.transcriptions.create(
                    file=file_tuple,
                    model=STT_MODEL,
                    language="te"
                )
                transcribed_text = getattr(re_tr, "text", "") or ""
                detected_lang = "te"
            elif raw_detected in hindi_group and raw_detected not in ("hindi", "hi"):
                logger.info(f"Remapping detected language '{raw_detected}' to Hindi ('hi') and re-transcribing...")
                re_tr = client.audio.transcriptions.create(
                    file=file_tuple,
                    model=STT_MODEL,
                    language="hi"
                )
                transcribed_text = getattr(re_tr, "text", "") or ""
                detected_lang = "hi"
            elif raw_detected in ("telugu", "te"):
                detected_lang = "te"
            elif raw_detected in ("hindi", "hi"):
                detected_lang = "hi"
            else:
                # Script detection fallback
                detected_lang = detect_script_language(transcribed_text)
        else:
            # Forced language
            whisper_lang = "te" if req_lang == "te" else ("hi" if req_lang == "hi" else "en")
            transcription = client.audio.transcriptions.create(
                file=file_tuple,
                model=STT_MODEL,
                language=whisper_lang
            )
            transcribed_text = getattr(transcription, "text", "") or ""
            detected_lang = req_lang

        transcribed_text = transcribed_text.strip()
        logger.info(f"Voice transcribed: '{transcribed_text}' (lang={detected_lang})")

        if not transcribed_text:
            return {
                "transcript": "",
                "lang": detected_lang if detected_lang in ("en", "hi", "te") else "en",
                "type": "unknown",
                "text": UNKNOWN_MESSAGES.get(detected_lang, UNKNOWN_MESSAGES["en"]),
                "options": [],
                "sources": [],
                "found": False,
                "error": "No speech detected in audio file."
            }

        res = process_bolo_conversation(transcribed_text, detected_lang, parsed_history)
        res["transcript"] = transcribed_text
        return res

    except Exception as e:
        logger.error(f"Top-level error in /ask-voice: {e}", exc_info=True)
        return {
            "transcript": "",
            "lang": "en" if lang == "auto" else lang,
            "type": "unknown",
            "text": UNKNOWN_MESSAGES["en"],
            "options": [],
            "sources": [],
            "found": False,
            "error": str(e)
        }
