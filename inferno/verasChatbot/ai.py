"""
Veras AI brain - adapted from the original verasChatbot/app.py (OpenAI + Gradio).

Works with any OpenAI-compatible provider. With no key at all it uses the free public
Pollinations endpoint (gpt-oss-20b), so the assistant works out of the box:

    Provider      Free?                      Key in inferno/.env       Get a key
    ----------    -------------------------  ------------------------  ------------------------------------
    pollinations  free, no key, no signup    (none - default)          https://pollinations.ai
    groq          free tier, no credit card  GROQ_API_KEY=gsk_...      https://console.groq.com/keys
    gemini        free tier, no credit card  GEMINI_API_KEY=...        https://aistudio.google.com/apikey
    huggingface   free monthly credits       HF_TOKEN=hf_...           https://huggingface.co/settings/tokens
    ollama        free, runs on this PC      (none)                    https://ollama.com  (AI_PROVIDER=ollama)
    openai        paid                       OPENAI_API_KEY=sk-...     https://platform.openai.com/api-keys

The first provider with a key is used, otherwise Pollinations; force one with AI_PROVIDER=<name>
(AI_PROVIDER=offline disables the AI and uses the built-in answers).

Voice and image work without any paid service:
  * Voice: the provider's speech-to-text if it has one, otherwise faster-whisper running locally.
  * Images: a vision model if the provider has one, otherwise local CLIP image search over the
    product photos (verasChatbot/visual_search.py).
Override models with AI_MODEL / AI_VISION_MODEL / AI_TRANSCRIBE_MODEL.

Changes from the original:
  * The model sees the conversation history and matching products from the CyberOptix
    database (flame.recommender), so it recommends real, purchasable laptops.
  * Replies follow the site language (Burmese on /my/ pages).
  * Voice uses the provider's speech-to-text (falls back to a local Whisper pipeline if
    `transformers` is installed); images are really sent to a vision model.
"""
import base64
import io
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)


def _load_dotenv():
    """Values from inferno/.env (environs keeps them out of os.environ, so read the file)."""
    try:
        from dotenv import dotenv_values
        return {k: v for k, v in dotenv_values(os.path.join(settings.BASE_DIR, ".env")).items() if v}
    except Exception:  # pragma: no cover - env file is optional
        return {}


_DOTENV = _load_dotenv()


def _setting(name, default=None):
    """Real environment variables win over inferno/.env."""
    return os.environ.get(name) or _DOTENV.get(name) or default


PROVIDERS = {
    "groq": {
        "label": "Groq (Llama)", "key": "GROQ_API_KEY", "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "vision": "meta-llama/llama-4-scout-17b-16e-instruct",
        "transcribe": "whisper-large-v3-turbo",
    },
    "gemini": {
        "label": "Google Gemini", "key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash", "vision": "gemini-2.5-flash", "transcribe": None,
    },
    "huggingface": {
        "label": "Hugging Face (gpt-oss-20b)", "key": "HF_TOKEN", "base_url": "https://router.huggingface.co/v1",
        "model": "openai/gpt-oss-20b", "vision": None, "transcribe": None,
    },
    "ollama": {
        "label": "Ollama (local)", "key": None, "base_url": "http://localhost:11434/v1",
        "model": "llama3.2", "vision": None, "transcribe": None,
    },
    "openai": {
        "label": "OpenAI", "key": "OPENAI_API_KEY", "base_url": None,
        "model": "gpt-4o-mini", "vision": "gpt-4o-mini", "transcribe": "whisper-1",
    },
    "pollinations": {
        "label": "Pollinations AI (free, gpt-oss-20b)", "key": None,
        "base_url": "https://text.pollinations.ai/openai",
        "model": "openai", "vision": None, "transcribe": None,
    },
}


def _valid_key(value):
    # Reject empty values and placeholders such as "sk-your-key-here".
    return bool(value) and "your" not in value.lower() and len(value) >= 20


def _pick_provider():
    forced = (_setting("AI_PROVIDER") or "").strip().lower()
    if forced in ("offline", "none", "off"):
        return None
    if forced in PROVIDERS:
        return forced
    for name, cfg in PROVIDERS.items():
        if cfg["key"] and _valid_key(_setting(cfg["key"])):
            return name
    return "pollinations"  # free default - no key needed


PROVIDER = _pick_provider()
_CFG = PROVIDERS.get(PROVIDER, {})
PROVIDER_LABEL = _CFG.get("label", "")
CHAT_MODEL = (_setting("AI_MODEL")
              or (_setting("OPENAI_MODEL") if PROVIDER == "openai" else None)
              or _CFG.get("model"))
VISION_MODEL = _setting("AI_VISION_MODEL") or _CFG.get("vision")
TRANSCRIBE_MODEL = _setting("AI_TRANSCRIBE_MODEL") or _CFG.get("transcribe")

_client = None
asr_pipeline = None


def get_client():
    """Lazily create the OpenAI-compatible client; None when no provider is configured."""
    global _client
    if _client is not None:
        return _client
    if not PROVIDER:
        return None
    key = _setting(_CFG["key"]) if _CFG.get("key") else "no-key-needed"
    if _CFG.get("key") and not _valid_key(key):
        return None
    try:
        import openai
    except ImportError:
        logger.warning("openai package not installed; Veras AI disabled")
        return None
    base_url = _setting("AI_BASE_URL") or _CFG.get("base_url") or _setting("OPENAI_BASE_URL")
    _client = openai.OpenAI(api_key=key, base_url=base_url, timeout=60.0, max_retries=2)
    return _client


def is_configured() -> bool:
    return get_client() is not None


# --------------------------------------------------------------------------- #
# Prompting
# --------------------------------------------------------------------------- #
STORE_FACTS = (
    "CyberOptix is a laptop marketplace in Myanmar with partner shops (Citicom, Unique, ICT, Innwa). "
    "Prices are in USD (shown in Kyat on Myanmar pages). Payment: PayPal, Stripe (cards), KBZPay, "
    "Cash on Delivery. Delivery anywhere in Myanmar or in-store pickup; shipping fee is calculated at "
    "checkout. Returns must be requested within 7 days of delivery; approved refunds take 3-5 business "
    "days to the original payment method. Support: +959 00090999, cyberoptix@gmail.com. "
    "Customers track orders under Profile -> Orders."
)


def system_prompt(lang: str = "en") -> str:
    language = (
        "Always reply in natural Burmese (Myanmar Unicode script). Keep brand and model names "
        "(e.g. ASUS ROG Strix, MacBook Air) and numbers in Latin script."
        if lang == "my" else
        "Reply in the language the customer writes in (English by default)."
    )
    return (
        "You are Veras, the friendly AI shopping assistant of CyberOptix.\n"
        f"{STORE_FACTS}\n"
        "When the customer is shopping, recommend ONLY products from the <catalog> list provided with "
        "their message - never invent products, prices or specs. Product cards for those items are "
        "shown under your reply, so explain briefly which fits best and why (2-5 sentences), using "
        "**bold** for product names. If the catalog list is empty or doesn't fit, say so and ask one "
        "short clarifying question (use, budget, brand). For general tech questions, answer helpfully "
        f"and concisely.\n{language}"
    )


def _catalog_block(products) -> str:
    if not products:
        return "<catalog>(no matching products)</catalog>"
    lines = [
        f"{i + 1}. {p['title']} | ${p['price']:,.0f} | CPU {p.get('cpu') or '-'} | RAM {p.get('ram') or '-'} | "
        f"brand {p.get('brand') or '-'} | shop {p.get('shop') or '-'} | "
        f"{'in stock' if p.get('in_stock', True) else 'out of stock'}"
        + (f" | match {p['score']}%" if p.get('score') is not None else "")
        for i, p in enumerate(products)
    ]
    return "<catalog>\n" + "\n".join(lines) + "\n</catalog>"


def _history_messages(history, limit=10):
    """Accepts [{'role': 'user'|'assistant'|'bot', 'content'|'text': str}, ...]."""
    out = []
    for turn in (history or [])[-limit:]:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        role = "assistant" if role in ("assistant", "bot") else "user" if role == "user" else None
        content = turn.get("content", turn.get("text"))
        if role and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content[:2000]})
    return out


def build_messages(user_message, history=None, products=None, lang="en"):
    return (
        [{"role": "system", "content": system_prompt(lang)}]
        + _history_messages(history)
        + [{"role": "user", "content": f"{user_message}\n\n{_catalog_block(products)}"}]
    )


def chat_reply(user_message, history=None, products=None, lang="en"):
    """Single (non-streaming) reply for the website widget. Returns text or None on failure."""
    client = get_client()
    if not client:
        return None
    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=build_messages(user_message, history, products, lang),
            max_tokens=1200,
            temperature=0.5,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception as exc:
        logger.warning("Veras AI call failed (%s): %s", PROVIDER, exc)
        return None


# --------------------------------------------------------------------------- #
# Gradio handlers (same signatures as the original app.py)
# --------------------------------------------------------------------------- #
def _safe_history(history):
    return list(history) if history else []


def _retrieve(user_message):
    """Find matching products for the message using the shared recommender."""
    try:
        from flame.recommender import parse_preferences, product_to_dict, score_products
        prefs = parse_preferences(user_message)
        if prefs.is_empty():
            return []
        return [product_to_dict(p, s, r) for p, s, r in score_products(prefs, limit=5)]
    except Exception as exc:  # DB not ready etc.
        logger.debug("retrieval failed: %s", exc)
        return []


def _error_text(exc):
    msg = str(exc).lower()
    if "402" in msg or "free limit" in msg or "429" in msg or "rate" in msg:
        return "The free AI allows one reply every 45 seconds - please wait a moment and ask again."
    if "quota" in msg or "billing" in msg:
        return "The AI provider's free quota or rate limit was reached. Please try again in a minute."
    if "api key" in msg or "401" in msg or "auth" in msg:
        return "The AI API key is invalid. Please check it in inferno/.env."
    return "I could not reach the AI backend right now. Please try again."


def get_response(user_message, history=None, lang="en"):
    """Streaming generator for gr.Chatbot(type='messages')."""
    history = _safe_history(history)
    user_message = (user_message or "").strip()
    if not user_message:
        yield history
        return
    base = history + [{"role": "user", "content": user_message}]
    client = get_client()
    if not client:
        yield base + [{"role": "assistant",
                       "content": "The AI is switched off (AI_PROVIDER=offline in inferno/.env)."}]
        return

    products = _retrieve(user_message)
    content = ""
    try:
        stream = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=build_messages(user_message, history, products, lang),
            max_tokens=1500,
            temperature=0.5,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content
                yield base + [{"role": "assistant", "content": content}]
        if products:
            links = "\n".join(f"- [{p['title']}]({p['url']}) - ${p['price']:,.0f}" for p in products[:4])
            yield base + [{"role": "assistant", "content": f"{content}\n\n{links}"}]
    except Exception as exc:
        logger.warning("Veras stream failed: %s", exc)
        yield base + [{"role": "assistant", "content": _error_text(exc)}]


def _load_audio_16k(path):
    """Decode any audio file (wav/webm/mp3...) to 16 kHz mono float32 with ffmpeg.

    faster-whisper's own decoder (PyAV) breaks with newer PyAV releases, and ffmpeg is
    needed by Gradio anyway, so decode through the ffmpeg CLI.
    """
    import subprocess
    import numpy as np
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True, timeout=120,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def voice_to_text(audio_path):
    if not audio_path:
        return ""
    client = get_client()
    if client and TRANSCRIBE_MODEL:
        try:
            with open(audio_path, "rb") as fh:
                result = client.audio.transcriptions.create(model=TRANSCRIBE_MODEL, file=fh)
            return (result.text or "").strip()
        except Exception as exc:
            logger.warning("Provider transcription failed, trying local Whisper: %s", exc)
    global asr_pipeline
    try:
        if asr_pipeline is None:
            from faster_whisper import WhisperModel  # free, runs locally on the CPU
            asr_pipeline = WhisperModel(_setting("WHISPER_MODEL", "base"), device="cpu", compute_type="int8")
        segments, _info = asr_pipeline.transcribe(_load_audio_16k(audio_path), beam_size=1, vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as exc:
        return f"Speech recognition failed: {exc}"


def handle_voice_text(text, history=None):
    """Answer an already-transcribed voice question (Gradio shows the transcript separately)."""
    if not text or text.startswith("Speech recognition failed"):
        yield _safe_history(history) + [{"role": "assistant", "content": text or "No speech detected."}]
        return
    yield from get_response(f"🎙️ {text}", history)


def handle_voice(audio_input, history=None):
    text = voice_to_text(audio_input)
    if not text or text.startswith("Speech recognition failed"):
        yield _safe_history(history) + [{"role": "assistant", "content": text or "No speech detected."}]
        return
    # Show what was heard, then answer it like a typed question.
    yield from get_response(f"🎙️ {text}", history)


def handle_image(image_input, history=None, image_prompt=""):
    """Send the image to a vision-capable model together with the question."""
    history = _safe_history(history)
    if image_input is None:
        return history
    prompt = (image_prompt or "").strip() or "Describe this image. If it shows a laptop or PC part, identify it."
    client = get_client()
    base = history + [{"role": "user", "content": f"🖼️ {prompt}"}]
    if not client:
        return base + [{"role": "assistant", "content": "No AI provider configured."}]
    if not VISION_MODEL:
        return base + [{"role": "assistant", "content": _image_search_reply(image_input, prompt, history)}]
    try:
        buf = io.BytesIO()
        img = image_input.convert("RGB")
        img.thumbnail((1280, 1280))
        img.save(buf, format="JPEG", quality=85)
        data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]},
            ],
            max_tokens=600,
        )
        answer = resp.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Veras image call failed: %s", exc)
        answer = _error_text(exc)
    return base + [{"role": "assistant", "content": answer}]


def _image_search_reply(image, prompt, history):
    """Free image search: CLIP finds look-alike products; the chat model explains the matches."""
    from . import visual_search
    if not visual_search.available():
        return "Image search needs the free `open_clip_torch` package (pip install open_clip_torch)."
    try:
        brand, kind = visual_search.describe(image)
        matches = visual_search.search(image, limit=4)
    except Exception as exc:
        logger.warning("Veras image search failed: %s", exc)
        return "Sorry, I couldn't analyse that image."
    from flame.recommender import product_to_dict
    products = [product_to_dict(p, score) for p, score in matches]
    seen = f"The photo looks like {kind}, most likely {brand}."
    question = f"{prompt}\n\n[Image search result] {seen} The visually closest products in our catalog are listed."
    answer = chat_reply(question, history, products)  # None if the AI is busy - matches still shown
    links = "\n".join(f"- [{p['title']}]({p['url']}) - ${p['price']:,.0f} ({p['score']}% visual match)"
                      for p in products)
    parts = [f"🔎 {seen}", answer, ("Closest products in our catalogue:\n" + links) if links else None]
    return "\n\n".join(x for x in parts if x)
