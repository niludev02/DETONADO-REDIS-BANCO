from django.urls import path
from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.index, name="index"),
    path("criar/", views.criar_jogo, name="criar"),
    path("<str:jogo_id>/editar/", views.editar_jogo, name="editar"),
    path("<str:jogo_id>/", views.detalhes_jogo, name="detalhes"),
]