from uuid import uuid4

from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from config.redis_conn import redis_conn
from .forms import JogoEdicaoForm, JogoForm
from .models import Jogo


def _eh_administrador(request):
    return bool(
        request.session.get("usuario_is_admin")
        or (
            request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )
    )


def index(request):
    jogos = [
        redis_conn.hgetall(chave)
        for chave in redis_conn.scan_iter(match="jogo:*")
    ]
    jogos = [jogo for jogo in jogos if jogo]
    for jogo in jogos:
        imagem = jogo.get("imagem", "")
        if imagem.startswith(("http://", "https://")):
            jogo["imagem_url"] = imagem
        elif imagem:
            jogo["imagem_url"] = default_storage.url(imagem)

    return render(
        request,
        "catalogo/index.html",
        {
            "jogos": jogos,
            "pode_criar_jogo": _eh_administrador(request),
        },
    )


def detalhes_jogo(request, jogo_id):
    jogo = redis_conn.hgetall(f"jogo:{jogo_id}")
    if not jogo:
        raise Http404("Jogo não encontrado.")

    imagem = jogo.get("imagem", "")
    if imagem.startswith(("http://", "https://")):
        jogo["imagem_url"] = imagem
    elif imagem:
        jogo["imagem_url"] = default_storage.url(imagem)

    return render(
        request,
        "catalogo/jogos/detalhes.html",
        {
            "jogo": jogo,
            "pode_editar_jogo": _eh_administrador(request),
        },
    )


@require_http_methods(["GET", "POST"])
def editar_jogo(request, jogo_id):
    if not _eh_administrador(request):
        if not request.user.is_authenticated and not request.session.get("usuario_id"):
            return redirect("usuarios:login")
        return HttpResponseForbidden("Apenas administradores podem editar jogos.")

    jogo = redis_conn.hgetall(f"jogo:{jogo_id}")
    if not jogo:
        raise Http404("Jogo não encontrado.")

    form = JogoEdicaoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        jogo=jogo,
    )

    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        imagem = dados["imagem"]
        caminho_imagem = None
        if imagem:
            formato = imagem.image.format.lower()
            extensao = "jpg" if formato == "jpeg" else formato
            caminho_imagem = default_storage.save(
                f"jogos/{uuid4().hex}.{extensao}",
                imagem,
            )

        Jogo.atualizar(
            jogo_id=jogo_id,
            titulo=dados["titulo"].strip(),
            descricao=dados["descricao"].strip(),
            genero=dados["genero"].strip(),
            plataformas=dados["plataformas"],
            desenvolvedora=dados["desenvolvedora"].strip(),
            distribuidora=dados["distribuidora"].strip(),
            data_lancamento=dados["data_lancamento"],
            status=dados["status"],
            imagem=caminho_imagem,
        )
        return redirect("catalogo:detalhes", jogo_id=jogo_id)

    imagem = jogo.get("imagem", "")
    if imagem.startswith(("http://", "https://")):
        jogo["imagem_url"] = imagem
    elif imagem:
        jogo["imagem_url"] = default_storage.url(imagem)

    return render(
        request,
        "catalogo/jogos/editar_jogo.html",
        {"form_jogo": form, "jogo": jogo},
    )


@require_http_methods(["GET", "POST"])
def criar_jogo(request):
    if not _eh_administrador(request):
        if not request.user.is_authenticated and not request.session.get("usuario_id"):
            return redirect("usuarios:login")
        return HttpResponseForbidden("Apenas administradores podem cadastrar jogos.")

    form = JogoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        imagem = dados["imagem"]
        formato = imagem.image.format.lower()
        extensao = "jpg" if formato == "jpeg" else formato
        caminho_imagem = default_storage.save(
            f"jogos/{uuid4().hex}.{extensao}",
            imagem,
        )
        Jogo.criar(
            titulo=dados["titulo"].strip(),
            descricao=dados["descricao"].strip(),
            genero=dados["genero"].strip(),
            plataformas=dados["plataformas"],
            desenvolvedora=dados["desenvolvedora"].strip(),
            distribuidora=dados["distribuidora"].strip(),
            imagem=caminho_imagem,
            data_lancamento=dados["data_lancamento"],
            status=dados["status"],
        )
        return redirect("catalogo:index")

    return render(
        request,
        "catalogo/jogos/criar_jogo.html",
        {
            "form_jogo": form,
        },
    )