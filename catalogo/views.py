import os
import unicodedata
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_POST

from config.redis_conn import redis_conn

from django.contrib.auth import get_user_model

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


def _esta_logado(request):
    return bool(request.user.is_authenticated or request.session.get("usuario_id"))


def _usuario_id(request):
    """Id do usuário logado como texto (o Redis guarda tudo como str)."""
    if request.user.is_authenticated:
        return str(request.user.id)
    return str(request.session.get("usuario_id", ""))


def _pode_editar_detonado(request, detonado):
    """Administrador edita qualquer um; usuário comum só o próprio."""
    if _eh_administrador(request):
        return True
    autor = detonado.get("autor_id", "")
    # bool(autor) evita liberar detonados antigos (sem autor) por "" == ""
    return bool(autor) and autor == _usuario_id(request)


def _negar_acesso(request, mensagem):
    """Não logado -> login. Logado sem permissão -> 403."""
    if not request.user.is_authenticated and not request.session.get("usuario_id"):
        return redirect("usuarios:login")
    return HttpResponseForbidden(mensagem)


def _url_imagem(caminho):
    """Aceita URL externa ou caminho salvo no storage."""
    if not caminho:
        return ""
    if caminho.startswith(("http://", "https://")):
        return caminho
    return default_storage.url(caminho)


def _salvar_imagem(imagem, pasta):
    if imagem is None:
        return ""

    try:
        imagem_obj = getattr(imagem, "image", None)
        if imagem_obj is not None:
            formato = imagem_obj.format.lower()
        else:
            imagem.seek(0)
            with Image.open(imagem) as img:
                formato = (img.format or "PNG").lower()
            imagem.seek(0)

        extensao = "jpg" if formato == "jpeg" else formato
        return default_storage.save(f"{pasta}/{uuid4().hex}.{extensao}", imagem)
    except (AttributeError, UnidentifiedImageError, ValueError):
        nome_arquivo = getattr(imagem, "name", "imagem")
        extensao = os.path.splitext(nome_arquivo)[1].lstrip(".") or "png"
        extensao = "jpg" if extensao.lower() == "jpeg" else extensao.lower()
        return default_storage.save(f"{pasta}/{uuid4().hex}.{extensao}", imagem)


def _listar_jogos_redis():
    jogos = []
    for chave in redis_conn.scan_iter(match="jogo:*"):
        if chave.endswith(":detonados"):
            continue
        dados = redis_conn.hgetall(chave)
        if dados:
            jogos.append(dados)
    return sorted(jogos, key=lambda jogo: jogo.get("titulo", "").lower())


def _listar_detonados_redis():
    detonados = []
    for chave in redis_conn.scan_iter(match="detonado:*"):
        if chave.endswith(":etapas"):
            continue
        dados = redis_conn.hgetall(chave)
        if dados:
            detonados.append(dados)
    return sorted(
        detonados, key=lambda detonado: detonado.get("data_detonado", ""), reverse=True
    )


def _normalizar_busca(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).casefold()
    return "".join(caractere for caractere in texto if not unicodedata.combining(caractere))


def _corresponde_busca(dados, campos, consulta):
    texto = " ".join(str(dados.get(campo, "")) for campo in campos)
    return consulta in _normalizar_busca(texto)


def index(request):
    consulta_original = request.GET.get("q", "").strip()
    consulta = _normalizar_busca(consulta_original)
    tipo = request.GET.get("tipo", "todos")
    if tipo == "detonados":
        parametros = request.GET.copy()
        parametros.pop("tipo", None)
        url_detonados = reverse("catalogo:detonados")
        query_string = parametros.urlencode()
        if query_string:
            url_detonados = f"{url_detonados}?{query_string}"
        return redirect(url_detonados)

    if tipo not in {"todos", "jogos", "detonados"}:
        tipo = "todos"

    todos_jogos = _listar_jogos_redis()
    jogos = todos_jogos if tipo in {"todos", "jogos"} else []
    detonados = []

    if consulta and jogos:
        campos_jogo = (
            "titulo",
            "descricao",
            "genero",
            "plataformas",
            "desenvolvedora",
            "distribuidora",
        )
        jogos = [
            jogo for jogo in jogos
            if _corresponde_busca(jogo, campos_jogo, consulta)
        ]

    if tipo in {"todos", "detonados"} and (consulta or tipo == "detonados"):
        jogos_por_id = {jogo.get("id", ""): jogo for jogo in todos_jogos}
        for detonado in _listar_detonados_redis():
            jogo = jogos_por_id.get(detonado.get("jogo_id", ""), {})
            detonado["jogo_titulo"] = jogo.get("titulo", "")
            campos_detonado = ("titulo", "descricao", "conteudo", "jogo_titulo")
            if not consulta or _corresponde_busca(detonado, campos_detonado, consulta):
                detonado["detonado_img_url"] = _url_imagem(
                    detonado.get("detonado_img") or jogo.get("imagem", "")
                )
                detonados.append(detonado)

    for jogo in jogos:
        jogo["imagem_url"] = _url_imagem(jogo.get("imagem", ""))

    return render(
        request,
        "catalogo/index.html",
        {
            "jogos": jogos,
            "detonados": detonados,
            "consulta": consulta_original,
            "tipo": tipo,
            "pode_criar_jogo": _eh_administrador(request),
        },
    )


def detalhes_jogo(request, jogo_id):
    jogo = redis_conn.hgetall(f"jogo:{jogo_id}")
    if not jogo:
        raise Http404("Jogo não encontrado.")

    detonados = []
    for detonado_id in redis_conn.smembers(f"jogo:{jogo_id}:detonados"):
        detonado = redis_conn.hgetall(f"detonado:{detonado_id}")
        if not detonado:
            continue
        detonado["descricao"] = (
            detonado.get("descricao") or detonado.get("conteudo", "")
        )
        detonado["detonado_img_url"] = _url_imagem(detonado.get("detonado_img", ""))
        detonados.append(detonado)

    jogo["imagem_url"] = _url_imagem(jogo.get("imagem", ""))

    return render(
        request,
        "catalogo/jogos/detalhes.html",
        {
            "jogo": jogo,
            "detonados": detonados,
            "pode_editar_jogo": _eh_administrador(request),
        },
    )


@require_http_methods(["GET", "POST"])
def editar_jogo(request, jogo_id):
    if not _eh_administrador(request):
        return _negar_acesso(request, "Apenas administradores podem editar jogos.")

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
        caminho_imagem = None
        if dados["imagem"]:
            caminho_imagem = _salvar_imagem(dados["imagem"], "jogos")

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

    jogo["imagem_url"] = _url_imagem(jogo.get("imagem", ""))

    return render(
        request,
        "catalogo/jogos/editar_jogo.html",
        {"form_jogo": form, "jogo": jogo},
    )


@require_http_methods(["GET", "POST"])
def criar_jogo(request):
    if not _eh_administrador(request):
        return _negar_acesso(request, "Apenas administradores podem cadastrar jogos.")

    form = JogoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        caminho_imagem = _salvar_imagem(dados["imagem"], "jogos")
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
        {"form_jogo": form},
    )


def view_detonados(request):
    consulta_original = request.GET.get("q", "").strip()
    consulta = _normalizar_busca(consulta_original)
    filtro_jogo = request.GET.get("jogo", "").strip()
    filtro_genero = request.GET.get("genero", "").strip()
    filtro_plataforma = request.GET.get("plataforma", "").strip()
    todos_detonados = []
    for chave in redis_conn.scan_iter(match="detonado:*"):
        if chave.endswith(":etapas"):
            continue
        detonado = redis_conn.hgetall(chave)
        if not detonado:
            continue

        jogo = redis_conn.hgetall(f"jogo:{detonado.get('jogo_id', '')}") if detonado.get("jogo_id") else {}
        detonado["descricao"] = (
            detonado.get("descricao") or detonado.get("conteudo", "")
        )
        detonado["genero"] = detonado.get("genero") or jogo.get("genero", "")
        detonado["plataformas"] = (
            detonado.get("plataformas") or jogo.get("plataformas", "")
        )
        detonado["jogo_titulo"] = jogo.get("titulo", "")
        campos_detonado = (
            "titulo",
            "descricao",
            "conteudo",
            "jogo_titulo",
            "genero",
            "plataformas",
        )
        if consulta and not _corresponde_busca(detonado, campos_detonado, consulta):
            continue
        detonado["detonado_img_url"] = _url_imagem(
            detonado.get("detonado_img") or jogo.get("imagem", "")
        )
        todos_detonados.append(detonado)

    jogos_disponiveis = sorted(
        {
            (detonado.get("jogo_id", ""), detonado["jogo_titulo"])
            for detonado in todos_detonados
            if detonado.get("jogo_id") and detonado["jogo_titulo"]
        },
        key=lambda jogo: _normalizar_busca(jogo[1]),
    )
    generos_disponiveis = sorted(
        {detonado["genero"].strip() for detonado in todos_detonados if detonado["genero"].strip()},
        key=_normalizar_busca,
    )
    plataformas_disponiveis = sorted(
        {
            plataforma.strip()
            for detonado in todos_detonados
            for plataforma in detonado["plataformas"].split(",")
            if plataforma.strip()
        },
        key=_normalizar_busca,
    )

    detonados = [
        detonado
        for detonado in todos_detonados
        if (not consulta or _corresponde_busca(
            detonado,
            ("titulo", "descricao", "conteudo", "jogo_titulo", "genero", "plataformas"),
            consulta,
        ))
        and (not filtro_jogo or detonado.get("jogo_id") == filtro_jogo)
        and (
            not filtro_genero
            or _normalizar_busca(detonado["genero"]) == _normalizar_busca(filtro_genero)
        )
        and (
            not filtro_plataforma
            or any(
                _normalizar_busca(plataforma.strip())
                == _normalizar_busca(filtro_plataforma)
                for plataforma in detonado["plataformas"].split(",")
            )
        )
    ]

    return render(
        request,
        "catalogo/detonados/detonados.html",
        {
            "detonados": detonados,
            "consulta": consulta_original,
            "filtro_jogo": filtro_jogo,
            "filtro_genero": filtro_genero,
            "filtro_plataforma": filtro_plataforma,
            "jogos_disponiveis": jogos_disponiveis,
            "generos_disponiveis": generos_disponiveis,
            "plataformas_disponiveis": plataformas_disponiveis,
            "pode_criar_detonado": _esta_logado(request),
        },
    )


def detalhes_detonado(request, detonado_id):
    detonado = redis_conn.hgetall(f"detonado:{detonado_id}")
    if not detonado:
        raise Http404("Detonado não encontrado.")

    detonado["descricao"] = (
        detonado.get("descricao") or detonado.get("conteudo", "")
    )
    detonado["detonado_img_url"] = _url_imagem(detonado.get("detonado_img", ""))

    etapas = []
    for etapa_id in redis_conn.lrange(f"detonado:{detonado_id}:etapas", 0, -1):
        etapa = redis_conn.hgetall(f"etapa:{etapa_id}")
        if etapa:
            etapa["etapa_img_url"] = _url_imagem(etapa.get("etapa_img", ""))
            etapas.append(etapa)

    autor_id = detonado.get("autor_id", "")
    autor = redis_conn.hgetall(f"usuario:{autor_id}") if autor_id else {}
    autor_nome = autor.get("nome", "")
    if not autor_nome and autor_id:
        usuario_model = get_user_model()
        try:
            usuario = usuario_model.objects.filter(pk=autor_id).only(
                "first_name", "username"
            ).first()
        except (TypeError, ValueError):
            usuario = None
        if usuario:
            autor_nome = usuario.get_full_name() or usuario.get_username()

    data_criacao = parse_datetime(detonado.get("data_detonado", ""))
    if data_criacao and timezone.is_naive(data_criacao):
        data_criacao = timezone.make_aware(data_criacao)
    if data_criacao:
        data_criacao = timezone.localtime(data_criacao)

    return render(
        request,
        "catalogo/detonados/detonado.html",
        {
            "detonado": detonado,
            "etapas": etapas,
            "autor_nome": autor_nome,
            "data_criacao": data_criacao,
            "pode_editar": _pode_editar_detonado(request, detonado),
        },
    )


@require_http_methods(["GET", "POST"])
def criar_detonado(request, jogo_id):
    jogo = redis_conn.hgetall(f"jogo:{jogo_id}")
    if not jogo:
        raise Http404("Jogo não encontrado.")
    if not jogo:
        raise Http404("Jogo não encontrado.")

    form = DetonadoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    etapa_titulos = request.POST.getlist("etapa_titulo")
    etapa_descricoes = request.POST.getlist("etapa_descricao")
    etapa_imagens = request.FILES.getlist("etapa_img")
    etapas_form = []
    erros_etapas = []
    etapas = []

    if request.method == "POST":
        total_etapas = max(len(etapa_titulos), len(etapa_descricoes), len(etapa_imagens), 1)
        for indice in range(total_etapas):
            titulo = etapa_titulos[indice].strip() if indice < len(etapa_titulos) else ""
            descricao = (
                etapa_descricoes[indice].strip()
                if indice < len(etapa_descricoes)
                else ""
            )
            imagem = (
                etapa_imagens[indice]
                if indice < len(etapa_imagens)
                else None
            )
            erro = ""
            if len(titulo) > 150:
                erro = "O título da etapa deve ter no máximo 150 caracteres."
            elif bool(titulo) != bool(descricao):
                erro = "Preencha o título e a descrição da etapa."
            elif titulo and descricao:
                etapas.append({
                    "titulo": titulo,
                    "descricao": descricao,
                    "etapa_img": _salvar_imagem(imagem, "detonados/etapas") if imagem else "",
                })
            elif imagem:
                etapas.append({
                    "titulo": titulo,
                    "descricao": descricao,
                    "etapa_img": _salvar_imagem(imagem, "detonados/etapas"),
                })
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
        caminho_imagem = _salvar_imagem(dados.get("detonado_img"), "detonados")

        detonado_id = Detonado.criar(
            jogo_id=jogo_id,
            titulo=dados["titulo"].strip(),
            descricao=dados["conteudo"].strip(),
            conteudo=dados["conteudo"].strip(),
            detonado_img=caminho_imagem,
            autor_id=_usuario_id(request),
        )
        redis_conn.sadd(f"jogo:{jogo_id}:detonados", detonado_id)
        for etapa in etapas:
            etapa_id = Etapa.criar(
                detonado_id=detonado_id,
                titulo=etapa["titulo"],
                descricao=etapa["descricao"],
                etapa_img=etapa.get("etapa_img", ""),
            )
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


@require_http_methods(["GET", "POST"])
def editar_detonado(request, jogo_id, detonado_id):
    if not _esta_logado(request):
        return redirect("usuarios:login")

    jogo = Jogo.obter(jogo_id)
    if not jogo:
        raise Http404("Jogo não encontrado.")

    detonado = Detonado.obter(detonado_id)
    if not detonado or detonado.get("jogo_id") != jogo_id:
        raise Http404("Detonado não encontrado.")

    if not _pode_editar_detonado(request, detonado):
        return HttpResponseForbidden("Você só pode editar os seus detonados.")

    etapas_existentes = detonado.get("etapas", [])
    etapas_por_id = {etapa["id"]: etapa for etapa in etapas_existentes if etapa.get("id")}
    form = DetonadoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        initial={
            "titulo": detonado.get("titulo", ""),
            "conteudo": detonado.get("conteudo") or detonado.get("descricao", ""),
        },
    )
    erros_etapas = []
    etapas_form = []
    etapas_atualizadas = []

    if request.method == "POST":
        ids = request.POST.getlist("etapa_id")
        titulos = request.POST.getlist("etapa_titulo")
        descricoes = request.POST.getlist("etapa_descricao")
        imagens = [
            request.FILES.get(f"etapa_img_{indice}")
            for indice in range(max(len(ids), len(titulos), len(descricoes)))
        ]
        remover_imagens = set(request.POST.getlist("remover_etapa_img"))
        total_etapas = max(len(ids), len(titulos), len(descricoes), len(imagens))
        ids_enviados = [etapa_id for etapa_id in ids if etapa_id]

        if len(ids_enviados) != len(set(ids_enviados)) or any(
            etapa_id not in etapas_por_id for etapa_id in ids_enviados
        ):
            erros_etapas.append("Uma ou mais etapas enviadas são inválidas.")

        for indice in range(total_etapas):
            etapa_id = ids[indice].strip() if indice < len(ids) else ""
            titulo_etapa = titulos[indice].strip() if indice < len(titulos) else ""
            descricao_etapa = (
                descricoes[indice].strip() if indice < len(descricoes) else ""
            )
            imagem = imagens[indice] if indice < len(imagens) else None
            etapa_existente = etapas_por_id.get(etapa_id) if etapa_id else None
            erro_etapa = ""

            if len(titulo_etapa) > 150:
                erro_etapa = "O título da etapa deve ter no máximo 150 caracteres."
            elif bool(titulo_etapa) != bool(descricao_etapa):
                erro_etapa = "Preencha o título e a descrição da etapa."
            elif not titulo_etapa and not descricao_etapa and not imagem:
                erro_etapa = "Preencha esta etapa ou remova-a."
            else:
                caminho_imagem = (
                    ""
                    if etapa_id in remover_imagens
                    else (etapa_existente or {}).get("etapa_img", "")
                )
                etapas_atualizadas.append(
                    {
                        "id": etapa_id,
                        "titulo": titulo_etapa,
                        "descricao": descricao_etapa,
                        "imagem": imagem,
                        "etapa_img": caminho_imagem,
                        "imagem_anterior": (etapa_existente or {}).get(
                            "etapa_img", ""
                        ),
                    }
                )

            etapas_form.append(
                {
                    "id": etapa_id,
                    "titulo": titulo_etapa,
                    "descricao": descricao_etapa,
                    "etapa_img_url": _url_imagem(
                        (etapa_existente or {}).get("etapa_img", "")
                    ),
                    "remover_imagem": etapa_id in remover_imagens,
                    "erro": erro_etapa,
                }
            )
            if erro_etapa:
                erros_etapas.append(erro_etapa)

        if not etapas_atualizadas:
            erros_etapas.append("Adicione pelo menos uma etapa completa.")
        if len(ids_enviados) != len(set(ids_enviados)) or any(
            etapa_id not in etapas_por_id for etapa_id in ids_enviados
        ):
            etapas_atualizadas = []

        if form.is_valid() and not erros_etapas:
            dados = form.cleaned_data
            imagem_detonado = dados.get("detonado_img")
            imagem_anterior = detonado.get("detonado_img", "")
            if imagem_detonado:
                caminho_detonado = _salvar_imagem(imagem_detonado, "detonados")
            elif request.POST.get("remover_detonado_img"):
                caminho_detonado = ""
            else:
                caminho_detonado = imagem_anterior

            Detonado.atualizar(
                detonado_id,
                titulo=dados["titulo"].strip(),
                descricao=dados["conteudo"].strip(),
                conteudo=dados["conteudo"].strip(),
                detonado_img=caminho_detonado,
            )

            ids_mantidos = {
                etapa["id"] for etapa in etapas_atualizadas if etapa["id"]
            }
            for etapa_existente in etapas_existentes:
                etapa_id = etapa_existente.get("id")
                if etapa_id and etapa_id not in ids_mantidos:
                    Etapa.excluir(etapa_id)

            for etapa in etapas_atualizadas:
                caminho_imagem = etapa["etapa_img"]
                imagem_anterior_etapa = etapa["imagem_anterior"]
                if etapa["imagem"]:
                    caminho_imagem = _salvar_imagem(
                        etapa["imagem"], "detonados/etapas"
                    )
                elif etapa["id"] in remover_imagens:
                    caminho_imagem = ""

                if etapa["id"]:
                    Etapa.atualizar(
                        etapa["id"],
                        etapa["titulo"],
                        etapa["descricao"],
                        etapa_img=caminho_imagem,
                    )
                else:
                    Etapa.criar(
                        detonado_id=detonado_id,
                        titulo=etapa["titulo"],
                        descricao=etapa["descricao"],
                        etapa_img=caminho_imagem,
                    )

                if (
                    imagem_anterior_etapa
                    and imagem_anterior_etapa != caminho_imagem
                    and not imagem_anterior_etapa.startswith(("http://", "https://"))
                ):
                    default_storage.delete(imagem_anterior_etapa)

            if (
                imagem_anterior
                and imagem_anterior != caminho_detonado
                and not imagem_anterior.startswith(("http://", "https://"))
            ):
                default_storage.delete(imagem_anterior)
            return redirect("catalogo:detalhes_detonado", detonado_id=detonado_id)
    else:
        for etapa in etapas_existentes:
            etapas_form.append(
                {
                    **etapa,
                    "etapa_img_url": _url_imagem(etapa.get("etapa_img", "")),
                    "erro": "",
                }
            )
        if not etapas_form:
            etapas_form.append(
                {"id": "", "titulo": "", "descricao": "", "etapa_img_url": "", "erro": ""}
            )

    return render(
        request,
        "catalogo/detonados/editar_detonado.html",
        {
            "jogo": jogo,
            "detonado": detonado,
            "form_detonado": form,
            "etapas_form": etapas_form,
            "erros_etapas": erros_etapas,
            "imagem_detonado_url": _url_imagem(detonado.get("detonado_img", "")),
            "remover_detonado_img": "1" in request.POST.getlist(
                "remover_detonado_img"
            ),
        },
    )


@require_POST
def excluir_detonado(request, detonado_id):
    detonado = redis_conn.hgetall(f"detonado:{detonado_id}")
    if not detonado:
        raise Http404("Detonado não encontrado.")

    if not _pode_editar_detonado(request, detonado):
        return _negar_acesso(request, "Você não pode excluir este detonado.")

    jogo_id = detonado.get("jogo_id", "")
    Detonado.excluir(detonado_id)
    if jogo_id and redis_conn.exists(f"jogo:{jogo_id}"):
        return redirect("catalogo:detalhes", jogo_id=jogo_id)
    return redirect("catalogo:detonados")