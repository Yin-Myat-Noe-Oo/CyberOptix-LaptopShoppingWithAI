from django.urls import path

from . import views

app_name = "verasChatbot"

urlpatterns = [
    path("", views.chat_page, name="chat-page"),
    path("api/", views.chat_api, name="chat-api"),
]
