"""
Veras Gradio studio - ported from the original verasChatbot/views.py.

Same features as before (text chat, voice upload -> speech-to-text, image
question), restyled to match the CyberOptix neon theme. It runs on its own
port (GRADIO_PORT, default 7860) in a background thread, started the first time
someone opens the full chat page, and is embedded there in an iframe.

`get_gradio_app()` is kept for inferno/asgi.py, which mounts it under ASGI.
"""
import logging
import os
import socket
import threading

from . import ai

logger = logging.getLogger(__name__)

GRADIO_PORT = int(os.environ.get("GRADIO_PORT", "7860"))
_lock = threading.Lock()
_started = False

CUSTOM_CSS = """
.gradio-container { background: transparent !important; max-width: 100% !important; font-family: Inter, system-ui, sans-serif !important; }
footer { display: none !important; }
.veras-head { display:flex; align-items:center; gap:12px; padding:4px 2px 8px; }
.veras-head .mark { width:40px; height:40px; border-radius:12px; display:grid; place-items:center; font-size:20px;
  background: linear-gradient(135deg,#22d3ee,#8b5cf6); box-shadow:0 6px 18px rgba(34,211,238,.35); }
.veras-head h2 { margin:0; font-size:1.1rem; } .veras-head p { margin:0; opacity:.7; font-size:.85rem; }
button.primary { background: linear-gradient(135deg,#22d3ee,#8b5cf6 55%,#ec4899) !important; border:0 !important; color:#fff !important; }
"""


def _theme():
    import gradio as gr
    return gr.themes.Base(
        primary_hue="cyan", secondary_hue="violet", neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    ).set(
        body_background_fill="#070b14",
        body_background_fill_dark="#070b14",
        body_text_color="#e7ecf7",
        body_text_color_dark="#e7ecf7",
        block_background_fill="#111a2e",
        block_background_fill_dark="#111a2e",
        block_border_color="#22304d",
        block_border_color_dark="#22304d",
        input_background_fill="#0c1222",
        input_background_fill_dark="#0c1222",
        button_secondary_background_fill="#172238",
        button_secondary_background_fill_dark="#172238",
        button_secondary_text_color="#e7ecf7",
        button_secondary_text_color_dark="#e7ecf7",
    )


def get_gradio_app():
    import gradio as gr

    with gr.Blocks(title="Veras AI Studio") as demo:
        gr.HTML(
            '<div class="veras-head"><div class="mark">🤖</div><div>'
            '<h2>Veras AI Studio</h2><p>Chat, talk or show a photo - powered by ' + (ai.PROVIDER_LABEL or 'AI') + '.</p></div></div>'
        )
        if not ai.is_configured():
            gr.Markdown("⚠️ **No AI key set** - add a free `GROQ_API_KEY` to `inferno/.env`.")

        chatbot_ui = gr.Chatbot(height=430, show_label=False,
                                avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=Veras"))

        with gr.Tabs():
            with gr.Tab("💬 Text"):
                with gr.Row():
                    user_input = gr.Textbox(placeholder="Ask me anything... e.g. gaming laptop under $1500",
                                            lines=1, max_lines=3, show_label=False, container=False, scale=5)
                    send_btn = gr.Button("Send", variant="primary", scale=1)
            with gr.Tab("🎙️ Voice"):
                voice_input = gr.Audio(sources=["microphone", "upload"], type="filepath", show_label=False)
                heard = gr.Textbox(label="Transcribed text (Whisper)", interactive=False, lines=1)
                voice_btn = gr.Button("Transcribe & ask", variant="primary")
            with gr.Tab("📷 Image"):
                with gr.Row():
                    image_input = gr.Image(type="pil", show_label=False, height=160)
                    image_prompt = gr.Textbox(placeholder="Ask about this image...", lines=2, show_label=False)
                image_btn = gr.Button("Analyze image", variant="primary")

        clear_btn = gr.Button("Clear conversation", variant="secondary", size="sm")

        user_input.submit(ai.get_response, [user_input, chatbot_ui], chatbot_ui).then(lambda: "", None, user_input)
        send_btn.click(ai.get_response, [user_input, chatbot_ui], chatbot_ui).then(lambda: "", None, user_input)
        # 1) speech -> text (shown to the user), 2) the text is answered like a typed question
        voice_btn.click(ai.voice_to_text, voice_input, heard).then(
            ai.handle_voice_text, [heard, chatbot_ui], chatbot_ui)
        image_btn.click(ai.handle_image, [image_input, chatbot_ui, image_prompt], chatbot_ui).then(
            lambda: (None, ""), None, [image_input, image_prompt])
        clear_btn.click(lambda: [], None, chatbot_ui)
    return demo


def _port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_started():
    """Start the Gradio server once (background thread). Returns True when it's available."""
    global _started
    if _started or _port_in_use(GRADIO_PORT):
        _started = True
        return True
    with _lock:
        if _started:
            return True
        try:
            import gradio  # noqa: F401
        except ImportError:
            logger.warning("gradio not installed; Veras AI Studio disabled")
            return False

        def _run():
            try:
                get_gradio_app().launch(server_name="0.0.0.0", server_port=GRADIO_PORT, share=False,
                                        theme=_theme(), css=CUSTOM_CSS,
                                        inbrowser=False, prevent_thread_lock=True, show_error=True)
            except Exception as exc:
                logger.exception("Gradio failed to start: %s", exc)

        threading.Thread(target=_run, daemon=True, name="veras-gradio").start()
        _started = True
        return True
