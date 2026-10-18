"""Provider-agnostic LLM client (OpenAI-compatible Chat Completions API, stdlib only).

Env:
  LLM_API_KEY   — required to enable AI features
  LLM_BASE_URL  — default https://api.openai.com/v1  (works with OpenRouter, Together, Groq, vLLM, Ollama /v1 ...)
  LLM_MODEL     — text model,   default gpt-4o-mini
  LLM_VISION_MODEL — vision model, default = LLM_MODEL
The rule: the LLM never produces design numbers. It reads images, explains, and phrases answers
from data we give it; all calculations stay in the deterministic engines.
"""
from __future__ import annotations
import base64
import json
import os
import re
import urllib.request
import urllib.error

_test_hook = None   # tests can set a callable(messages, model, json_mode) -> str


def enabled() -> bool:
    return bool(os.getenv("LLM_API_KEY")) or _test_hook is not None


class LLMError(RuntimeError):
    pass


def chat(messages, model=None, json_mode=False, max_tokens=1200, temperature=0.1, timeout=60) -> str:
    model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
    if _test_hook:
        return _test_hook(messages, model, json_mode)
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise LLMError("ميزات الذكاء الاصطناعي غير مفعلة (ضع LLM_API_KEY في الإعدادات)")
    url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"خطأ من مزود الذكاء الاصطناعي ({e.code})")
    except Exception as e:  # network, timeout
        raise LLMError(f"تعذر الاتصال بمزود الذكاء الاصطناعي: {e.__class__.__name__}")
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError("رد غير متوقع من النموذج")


def image_part(png_or_jpg: bytes, mime="image/jpeg"):
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(png_or_jpg).decode()}"}}


def vision(prompt: str, image: bytes, system: str = "", json_mode=True, mime="image/jpeg") -> str:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": [{"type": "text", "text": prompt}, image_part(image, mime)]})
    return chat(msgs, model=os.getenv("LLM_VISION_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini"), json_mode=json_mode)


def parse_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise LLMError("النموذج لم يرجع JSON صالح")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        raise LLMError("النموذج رجع JSON غير صالح")
