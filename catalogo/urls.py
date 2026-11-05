from django.urls import path
from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.index, name="index"),
    path("criar/", views.criar_jogo, name="criar"),
    path("detonados/", views.view_detonados, name="detonados"),
    path("detonados/<str:detonado_id>/", views.detalhes_detonado, name="detalhes_detonado"),
    path("<str:jogo_id>/detonado/criar/", views.criar_detonado, name="criar_detonado"),
    path("<str:jogo_id>/detonado/<str:detonado_id>/editar/", views.editar_detonado, name="editar_detonado"),
    path("<str:jogo_id>/editar/", views.editar_jogo, name="editar"),
    path("<str:jogo_id>/", views.detalhes_jogo, name="detalhes"),
]