import os
from django.core.asgi import get_asgi_application
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
import gradio as gr

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inferno.settings")  # ✅ your real project name

django_asgi_app = get_asgi_application()

from verasChatbot.gradio_ui import get_gradio_app

fastapi_app = FastAPI()

gradio_app = get_gradio_app()

app = gr.mount_gradio_app(
    fastapi_app,
    gradio_app,
    path="/verasChatbot"
)
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

app = FastAPI()

# Mount Django correctly as a sub-application (no WSGIMiddleware)
app.mount("/verasChatbot", django_asgi_app)

