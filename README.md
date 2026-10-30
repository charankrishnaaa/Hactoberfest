# Bolo — Voice Assistant for Indian Government Services

> **Bolo** (Hindi: "Speak") is a voice-first multilingual AI assistant designed to help Indian citizens discover, understand, and apply for government welfare schemes and citizen services in **English**, **Hindi (हिन्दी)**, and **Telugu (తెలుగు)**.

---

## 🌟 What It Does

- **Multilingual Voice & Text Input**: Accepts natural speech recordings (via browser MediaRecorder in WebM/MP4) or typed text questions.
- **RAG Knowledge Retrieval**: Extracts and indexes government schemes from `schemes.json` using TF-IDF vectorization and cosine similarity. It handles any JSON schema structure generically.
- **Cross-Lingual Querying**: Translates regional Indian language questions (Hindi, Telugu) into English for scheme search, then synthesizes answers back in the user's native language.
- **Voice-Optimized, Grounded Answers**: Answers strictly from official scheme context in 1–3 short, clear sentences without markdown or bullet points, suitable for text-to-speech (TTS) readout.
- **Official Sources & Helpline Fallback**: Returns official government portal URLs for verified schemes. If a scheme is not in the knowledge base, it directs the citizen to official helplines (`1800-180-1551` / CSC Mee Seva centres).

---

## 🤖 Open-Source AI Models Used

This project runs open-source state-of-the-art models hosted with ultra-low latency on **Groq LPUs**:

| Task | Open-Source Model | Description |
| :--- | :--- | :--- |
| **Speech-to-Text (STT)** | `whisper-large-v3` | OpenAI's open-weights Whisper model; highly accurate across Indian languages and English accents. |
| **Reasoning & Generation** | `llama-3.1-8b-instant` | Meta's open-weights LLaMA 3.1 8B parameter model; handles translation, scheme grounding, and concise conversational response generation. |
| **Semantic Retrieval** | `scikit-learn` TF-IDF | Open-source vector indexing and cosine similarity for instant on-device scheme matching without complex vector database setups. |

---

## 🚀 How to Run

### 1. Prerequisites
- Ubuntu Linux (or any Linux/macOS environment)
- Python 3.10+
- A free [Groq API Key](https://console.groq.com)

### 2. Setup Virtual Environment & Install Dependencies

```bash
# Clone/navigate to project directory
cd bolo-backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Configure API Key

Export your Groq API key in your shell:
```bash
export GROQ_API_KEY="gsk_your_groq_api_key_here"
```

*Or* create a `.env` file in the project root:
```bash
echo 'GROQ_API_KEY="gsk_your_groq_api_key_here"' > .env
```

### 4. Start the Server

```bash
uvicorn main:app --reload --port 8000
```

The server will start at `http://127.0.0.1:8000`.

---

## 📡 API Reference

### 1. Health Check
Checks if the server is healthy and reports how many schemes are loaded.

- **URL**: `GET /health`
- **Response**:
```json
{
  "status": "ok",
  "schemes_loaded": 3
}
```

### 2. Ask Text Query
Ask a question in English, Hindi, or Telugu via JSON.

- **URL**: `POST /ask-text`
- **Headers**: `Content-Type: application/json`
- **Body**:
```json
{
  "question": "How much financial support is given under PM Kisan?",
  "lang": "en"
}
```
*(Valid `lang` values: `"en"`, `"hi"`, `"te"`)*

- **Response**:
```json
{
  "question": "How much financial support is given under PM Kisan?",
  "answer": "PM-KISAN provides income support of 6,000 rupees per year to farmer families. It is paid in three equal instalments of 2,000 rupees directly to your bank account.",
  "sources": [
    {
      "name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
      "url": "https://pmkisan.gov.in"
    }
  ],
  "found": true
}
```

### 3. Ask Voice Query
Transcribe an audio recording and answer the citizen's query.

- **URL**: `POST /ask-voice`
- **Method**: Multipart Form Data (`multipart/form-data`)
- **Fields**:
  - `audio`: Audio file (WebM, MP4, WAV, OGG, or MP3 from browser MediaRecorder)
  - `lang`: `"en"` | `"hi"` | `"te"`

- **Example curl**:
```bash
curl -X POST "http://127.0.0.1:8000/ask-voice" \
  -F "audio=@recording.webm" \
  -F "lang=hi"
```

- **Response**:
```json
{
  "question": "पीएम किसान में कितने पैसे मिलते हैं?",
  "answer": "पीएम-किसान योजना के तहत किसान परिवारों को हर साल छह हजार रुपये की आर्थिक सहायता मिलती है। यह राशि दो-दो हजार रुपये की तीन किस्तों में सीधे बैंक खाते में दी जाती है।",
  "sources": [
    {
      "name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
      "url": "https://pmkisan.gov.in"
    }
  ],
  "found": true
}
```

---

## 📁 Project Structure

```text
bolo-backend/
├── main.py              # FastAPI application, scheme loader, TF-IDF search, AI pipeline
├── schemes.json         # Government schemes dataset (read generically)
├── requirements.txt     # Python dependencies
├── .gitignore           # Git ignore rules for venv, cache, and .env
├── LICENSE              # MIT License
└── README.md            # Documentation & API guide
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
