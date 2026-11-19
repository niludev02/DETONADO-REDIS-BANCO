from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("cadastro/", views.cadastro_view, name="cadastro"),
    path("perfil/", views.perfil_view, name="perfil"),
    path("perfil/administracao/jogos/", views.administracao_jogos, name="administracao_jogos"),
    path("perfil/administracao/jogos/<str:jogo_id>/excluir/", views.excluir_jogo_administracao, name="excluir_jogo_administracao"),
    path("perfil/editar/", views.personalização_perfil, name="personalização_perfil"),
    path("perfil/seguranca/", views.seguranca_perfil, name="seguranca_perfil"),
]
