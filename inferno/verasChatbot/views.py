import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import translation
from django.views.decorators.http import require_http_methods

from . import ai
from .engine import respond, suggestions

SESSION_KEY = "veras_context"
SUPPORTED_LANGS = {"en", "my"}


def chat_page(request):
    """Full-page assistant: the Veras chat plus your Gradio voice & image studio."""
    from . import gradio_ui
    gradio_url = gradio_ui.ensure_started()  # starts Gradio in a background thread on first visit
    host = request.get_host().split(":")[0]
    return render(request, "flame/chatbot.html.html", {
        "suggestions": suggestions(),
        "gradio_src": f"{request.scheme}://{host}:{gradio_ui.GRADIO_PORT}/" if gradio_url else "",
        "ai_ready": ai.is_configured(),
        "ai_provider": ai.PROVIDER_LABEL,
    })


@require_http_methods(["GET", "POST"])
def chat_api(request):
    """
    POST JSON {"message": "...", "history": [{"role": "user"|"bot", "text": "..."}], "lang": "en"|"my"}
    (GET ?message=... is kept for the old /chatbot-reply frontend).
    Returns {"reply", "response", "products", "suggestions", "ai"}.
    """
    if request.method == "POST":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        message = str(payload.get("message", ""))[:1000]
        history = payload.get("history") or []
        lang = payload.get("lang")
        if payload.get("reset"):
            request.session.pop(SESSION_KEY, None)
            if not message:
                return JsonResponse({"ok": True})
    else:
        message = request.GET.get("message", "")[:1000]
        history, lang = [], request.GET.get("lang")

    if lang not in SUPPORTED_LANGS:
        lang = translation.get_language_from_request(request)
        lang = lang if lang in SUPPORTED_LANGS else "en"
    if not isinstance(history, list):
        history = []

    with translation.override(lang):
        result = respond(message, history, request.session.get(SESSION_KEY), lang=lang)
    request.session[SESSION_KEY] = result.pop("context", {})

    if request.user.is_authenticated and message:
        try:
            from flame.models import UserBehavior
            UserBehavior.objects.create(user=request.user, action="search",
                                        search_query=message[:200],
                                        session_id=request.session.session_key or "")
        except Exception:
            pass

    result["response"] = result["reply"]  # backwards compatible key
    result["ai"] = ai.is_configured()
    return JsonResponse(result)
