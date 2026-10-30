#!/usr/bin/env python3
"""
Test suite for Bolo Backend API.
Uses Python standard library ONLY (urllib, json, sys).
Tests all core endpoints, multilingual queries, eligibility helper conversation flow, and out-of-scope handling.
"""

import urllib.request
import urllib.error
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def log_test(name: str, passed: bool, detail: str = ""):
    status = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
    print(f"[{status}] {name}")
    if detail:
        print(f"       -> {detail}")

def http_get(path: str):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Bolo-Test/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def http_post_json(path: str, data: dict):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Bolo-Test/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def run_tests():
    print("=" * 60)
    print("RUNNING BOLO BACKEND API VERIFICATION SUITE")
    print(f"Target URL: {BASE_URL}")
    print("=" * 60)

    total = 0
    passed = 0

    # Test 1: GET /health
    total += 1
    try:
        status, data = http_get("/health")
        ok = status == 200 and data.get("status") == "ok" and data.get("schemes_loaded", 0) > 100
        log_test("GET /health", ok, f"status={status}, schemes_loaded={data.get('schemes_loaded')}")
        if ok: passed += 1
    except Exception as e:
        log_test("GET /health", False, str(e))

    # Test 2: GET /categories
    total += 1
    try:
        status, data = http_get("/categories")
        ok = status == 200 and isinstance(data, list) and len(data) >= 10
        farmer_cat = next((c for c in data if c.get("name") == "Farmers"), None)
        ok = ok and farmer_cat is not None and farmer_cat.get("count", 0) > 0
        log_test("GET /categories", ok, f"Categories returned: {len(data)}, Farmers count: {farmer_cat.get('count') if farmer_cat else 'N/A'}")
        if ok: passed += 1
    except Exception as e:
        log_test("GET /categories", False, str(e))

    # Test 3: GET /schemes
    total += 1
    try:
        status, data = http_get("/schemes?category=Farmers")
        ok = status == 200 and isinstance(data, list) and len(data) > 0
        first = data[0] if data else {}
        has_fields = all(k in first for k in ("id", "name", "short", "category", "benefit", "url"))
        ok = ok and has_fields
        log_test("GET /schemes?category=Farmers", ok, f"Found {len(data)} farmer schemes; sample: {first.get('name')}")
        if ok: passed += 1
    except Exception as e:
        log_test("GET /schemes?category=Farmers", False, str(e))

    # Test 4: GET /schemes/{id}
    total += 1
    try:
        status, data = http_get("/schemes/SCHEME_001")
        ok = status == 200 and data.get("id") == "SCHEME_001" and "documents" in data and "application_url" in data
        log_test("GET /schemes/SCHEME_001", ok, f"Name: {data.get('scheme_name')}")
        if ok: passed += 1
    except Exception as e:
        log_test("GET /schemes/SCHEME_001", False, str(e))

    # Test 5: English eligibility question (Must trigger follow-up question or answer with sources)
    total += 1
    bolo_first_reply = None
    try:
        req_data = {
            "question": "Can I get financial help as a farmer under PM-KISAN? Am I eligible?",
            "lang": "en",
            "history": []
        }
        status, data = http_post_json("/ask-text", req_data)
        bolo_first_reply = data
        ok = status == 200 and data.get("found") is True and data.get("lang") == "en"
        # It should either ask a follow-up about land holding or give answer
        is_q_or_a = data.get("type") in ("question", "answer")
        ok = ok and is_q_or_a and len(data.get("text", "")) > 10
        detail = f"type={data.get('type')}, options={data.get('options')}, text={data.get('text')[:60]}..."
        log_test("POST /ask-text (English Eligibility Query)", ok, detail)
        if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-text (English Eligibility Query)", False, str(e))

    # Test 6: Answering the follow-up question with history
    total += 1
    try:
        history = [
            {"role": "user", "text": "Can I get financial help as a farmer under PM-KISAN? Am I eligible?", "kind": "question"}
        ]
        if bolo_first_reply:
            history.append({
                "role": "bolo",
                "text": bolo_first_reply.get("text", "Do you own cultivable agricultural land?"),
                "kind": bolo_first_reply.get("type", "question")
            })
        
        req_data = {
            "question": "Yes, I own 2 acres of cultivable farmland in my village.",
            "lang": "en",
            "history": history
        }
        status, data = http_post_json("/ask-text", req_data)
        ok = status == 200 and data.get("found") is True
        # Now it should deliver an answer
        has_mention = "kisan" in data.get("text", "").lower() or "pm" in data.get("text", "").lower() or len(data.get("sources", [])) > 0
        ok = ok and has_mention
        detail = f"type={data.get('type')}, text={data.get('text')[:70]}..."
        log_test("POST /ask-text (Follow-up Answer Flow)", ok, detail)
        if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-text (Follow-up Answer Flow)", False, str(e))

    # Test 7: Hindi spoken question
    total += 1
    try:
        req_data = {
            "question": "आयुष्मान भारत कार्ड से क्या लाभ मिलता है और कितना इलाज मुफ्त होता है?",
            "lang": "hi",
            "history": []
        }
        status, data = http_post_json("/ask-text", req_data)
        ok = status == 200 and data.get("found") is True and data.get("lang") == "hi"
        # Check Devanagari script in text
        has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in data.get("text", ""))
        ok = ok and has_devanagari
        detail = f"lang={data.get('lang')}, text={data.get('text')[:60]}..."
        log_test("POST /ask-text (Spoken Hindi Query)", ok, detail)
        if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-text (Spoken Hindi Query)", False, str(e))

    # Test 8: Telugu spoken question
    total += 1
    try:
        req_data = {
            "question": "రైతులకు పీఎం కిసాన్ పథకంలో ఎంత సహాయం అందుతుంది?",
            "lang": "te",
            "history": []
        }
        status, data = http_post_json("/ask-text", req_data)
        ok = status == 200 and data.get("found") is True and data.get("lang") == "te"
        has_telugu = any(0x0C00 <= ord(c) <= 0x0C7F for c in data.get("text", ""))
        ok = ok and has_telugu
        detail = f"lang={data.get('lang')}, text={data.get('text')[:60]}..."
        log_test("POST /ask-text (Spoken Telugu Query)", ok, detail)
        if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-text (Spoken Telugu Query)", False, str(e))

    # Test 9: Auto-detect Telugu question
    total += 1
    try:
        req_data = {
            "question": "ఆయుష్మాన్ భారత్ కార్డు ద్వారా ఎంతవరకు ఉచిత వైద్యం పొందవచ్చు?",
            "lang": "auto",
            "history": []
        }
        status, data = http_post_json("/ask-text", req_data)
        ok = status == 200 and data.get("lang") == "te" and data.get("found") is True
        has_telugu = any(0x0C00 <= ord(c) <= 0x0C7F for c in data.get("text", ""))
        ok = ok and has_telugu
        detail = f"auto-detected lang={data.get('lang')}, text={data.get('text')[:60]}..."
        log_test("POST /ask-text (Auto-detect Telugu Script)", ok, detail)
        if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-text (Auto-detect Telugu Script)", False, str(e))

    # Test 10: Out of Scope question (Passport application)
    total += 1
    try:
        req_data = {
            "question": "How do I apply for an Indian passport and international visa?",
            "lang": "en",
            "history": []
        }
        status, data = http_post_json("/ask-text", req_data)
        ok = status == 200 and data.get("type") == "unknown" and data.get("found") is False
        ok = ok and len(data.get("sources", [])) == 0
        detail = f"type={data.get('type')}, found={data.get('found')}, text={data.get('text')[:60]}..."
        log_test("POST /ask-text (Out of Scope / Passport -> Unknown)", ok, detail)
        if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-text (Out of Scope / Passport -> Unknown)", False, str(e))

    # Test 11: POST /ask-voice (Multipart Audio Pipeline via Whisper)
    total += 1
    try:
        import wave, struct, io
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(struct.pack("<h", 0) * 16000)
        wav_bytes = wav_buf.getvalue()

        boundary = "----BoloTestBoundary9876"
        body = io.BytesIO()
        body.write(f"--{boundary}\r\n".encode())
        body.write(b'Content-Disposition: form-data; name="audio"; filename="test.wav"\r\n')
        body.write(b"Content-Type: audio/wav\r\n\r\n")
        body.write(wav_bytes)
        body.write(f"\r\n--{boundary}\r\n".encode())
        body.write(b'Content-Disposition: form-data; name="lang"\r\n\r\n')
        body.write(b"auto\r\n")
        body.write(f"\r\n--{boundary}\r\n".encode())
        body.write(b'Content-Disposition: form-data; name="history"\r\n\r\n')
        body.write(b"[]\r\n")
        body.write(f"\r\n--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            f"{BASE_URL}/ask-voice",
            data=body.getvalue(),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "Bolo-Test/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ok = resp.status == 200 and "type" in data and "transcript" in data
            detail = f"type={data.get('type')}, transcript={repr(data.get('transcript'))}"
            log_test("POST /ask-voice (Multipart Audio via Whisper)", ok, detail)
            if ok: passed += 1
    except Exception as e:
        log_test("POST /ask-voice (Multipart Audio via Whisper)", False, str(e))

    print("=" * 60)
    print(f"TEST RESULTS: {passed}/{total} PASSED")
    print("=" * 60)

    if passed == total:
        print("\033[92mALL BACKEND API CHECKS PASSED SUCCESSFULLY!\033[0m")
        return 0
    else:
        print(f"\033[91mSOME TESTS FAILED ({total - passed} failed)\033[0m")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
