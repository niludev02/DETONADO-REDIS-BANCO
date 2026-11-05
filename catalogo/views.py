from uuid import uuid4

from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from config.redis_conn import redis_conn
from .forms import DetonadoForm, JogoEdicaoForm, JogoForm
from .models import Detonado, Etapa, Jogo

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
        if chave.count(":") == 1
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

def view_detonados(request):
    detonados = []
    for chave in redis_conn.scan_iter(match="detonado:*"):
        if chave.count(":") != 1:
            continue

        detonado = redis_conn.hgetall(chave)
        if not detonado:
            continue

        detonado.setdefault("id", chave.split(":", 1)[1])
        detonado["descricao"] = (
            detonado.get("descricao") or detonado.get("conteudo", "")
        )

        jogo = (
            redis_conn.hgetall(f"jogo:{detonado['jogo_id']}")
            if detonado.get("jogo_id")
            else {}
        )
        detonado["genero"] = detonado.get("genero") or jogo.get("genero", "")
        detonado["plataformas"] = (
            detonado.get("plataformas") or jogo.get("plataformas", "")
        )

        imagem = detonado.get("detonado_img", "")
        detonado["detonado_img_url"] = default_storage.url(imagem) if imagem else ""
        detonados.append(detonado)

    return render(
        request,
        "catalogo/detonados/detonados.html",
        {
            "detonados": detonados,
            "pode_criar_detonado": _eh_administrador(request),
        },
    )


def detalhes_detonado(request, detonado_id):
    detonado = redis_conn.hgetall(f"detonado:{detonado_id}")
    if not detonado:
        raise Http404("Detonado não encontrado.")

    detonado["descricao"] = (
        detonado.get("descricao") or detonado.get("conteudo", "")
    )
    imagem = detonado.get("detonado_img", "")
    detonado["detonado_img_url"] = default_storage.url(imagem) if imagem else ""
    etapa_ids = redis_conn.lrange(f"detonado:{detonado_id}:etapas", 0, -1)
    etapas = [
        redis_conn.hgetall(f"etapa:{etapa_id}")
        for etapa_id in etapa_ids
    ]
    etapas = [etapa for etapa in etapas if etapa]

    return render(
        request,
        "catalogo/detonados/detonado.html",
        {"detonado": detonado, "etapas": etapas},
    )


@require_http_methods(["GET", "POST"])
def criar_detonado(request, jogo_id):

    jogo = redis_conn.hgetall(f"jogo:{jogo_id}")
    if not jogo:
        raise Http404("Jogo não encontrado.")

    form = DetonadoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    etapa_titulos = request.POST.getlist("etapa_titulo")
    etapa_descricoes = request.POST.getlist("etapa_descricao")
    etapas_form = []
    erros_etapas = []
    etapas = []

    if request.method == "POST":
        total_etapas = max(len(etapa_titulos), len(etapa_descricoes), 1)
        for indice in range(total_etapas):
            titulo = etapa_titulos[indice].strip() if indice < len(etapa_titulos) else ""
            descricao = (
                etapa_descricoes[indice].strip()
                if indice < len(etapa_descricoes)
                else ""
            )
            erro = ""
            if len(titulo) > 150:
                erro = "O título da etapa deve ter no máximo 150 caracteres."
            elif bool(titulo) != bool(descricao):
                erro = "Preencha o título e a descrição da etapa."
            elif titulo and descricao:
                etapas.append({"titulo": titulo, "descricao": descricao})
            etapas_form.append(
                {"titulo": titulo, "descricao": descricao, "erro": erro}
            )
            if erro:
                erros_etapas.append(erro)

        if not etapas:
            erros_etapas.append("Adicione pelo menos uma etapa completa.")
    else:
        etapas_form = [{"titulo": "", "descricao": "", "erro": ""}]

    if request.method == "POST" and form.is_valid() and not erros_etapas:
        dados = form.cleaned_data
        imagem = dados["detonado_img"]
        formato = imagem.image.format.lower()
        extensao = "jpg" if formato == "jpeg" else formato
        caminho_imagem = default_storage.save(
            f"detonados/{uuid4().hex}.{extensao}",
            imagem,
        )
        detonado_id = Detonado.criar(
            jogo_id=jogo_id,
            titulo=dados["titulo"].strip(),
            descricao=dados["conteudo"].strip(),
            conteudo=dados["conteudo"].strip(),
            detonado_img=caminho_imagem,
        )
        redis_conn.sadd(f"jogo:{jogo_id}:detonados", detonado_id)
        for etapa in etapas:
            etapa_id = Etapa.criar(
                detonado_id=detonado_id,
                titulo=etapa["titulo"],
                descricao=etapa["descricao"],
            )
            redis_conn.rpush(f"detonado:{detonado_id}:etapas", etapa_id)
        return redirect("catalogo:detalhes_detonado", detonado_id=detonado_id)

    return render(
        request,
        "catalogo/detonados/criar_detonado.html",
        {
            "jogo": jogo,
            "form_detonado": form,
            "etapas_form": etapas_form,
            "erros_etapas": erros_etapas,
        },
    )

def editar_detonado(request, jogo_id, detonado_id):
    jogo = redis_conn.hgetall(f"jogo:{jogo_id}")
    if not jogo:
        raise Http404("Jogo não encontrado.")

    detonado = redis_conn.hgetall(f"detonado:{detonado_id}")
    if not detonado or detonado.get("jogo_id") != jogo_id:
        raise Http404("Detonado não encontrado.")

    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        conteudo = request.POST.get("conteudo", "").strip()

        if titulo and conteudo:
            dados_detonado = {
                "titulo": titulo,
                "conteudo": conteudo,
            }
            redis_conn.hset(
                f"detonado:{detonado_id}",
                mapping=dados_detonado
            )
            return redirect("catalogo:detalhes", jogo_id=jogo_id)

    return render(
        request,
        "catalogo/detonados/editar_detonado.html",
        {"jogo": jogo, "detonado": detonado},
    )