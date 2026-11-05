
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.forms import EmailField
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from uuid import uuid4

from .forms import CadastroForm, PersonalizacaoPerfilForm
from config.redis_conn import redis_conn


@require_http_methods(["GET", "POST"])
def login_view(request):
    contexto = {
        "email": "",
        "erro": "",
        "next": request.GET.get("next", ""),
    }
    if request.method == "GET":
        contexto["cadastro_sucesso"] = request.session.pop(
            "cadastro_sucesso", False
        )

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        senha = request.POST.get("senha", "")
        destino = request.POST.get("next", "")
        contexto.update({"email": email, "next": destino})

        usuario_model = get_user_model()
        usuarios = (
            list(usuario_model.objects.filter(email__iexact=email)[:2])
            if email
            else []
        )
        autenticado = False

        if usuarios:
            if len(usuarios) == 1 and senha:
                usuario = authenticate(
                    request,
                    **{
                        usuario_model.USERNAME_FIELD: usuarios[0].get_username(),
                        "password": senha,
                    },
                )
                if usuario is not None:
                    auth_login(request, usuario)
                    autenticado = True
        else:
            usuario_id = redis_conn.get(f"usuario:email:{email}") if email else None
            usuario = redis_conn.hgetall(f"usuario:{usuario_id}") if usuario_id else {}
            if usuario and check_password(senha, usuario.get("senha", "")):
                request.session.cycle_key()
                request.session["usuario_id"] = usuario_id
                request.session["usuario_nome"] = usuario.get("nome", "")
                request.session["usuario_email"] = usuario.get("email", email)
                request.session["usuario_is_admin"] = usuario.get("is_admin") == "1"
                foto_perfil = usuario.get("foto_perfil")
                request.session["usuario_foto_perfil"] = (
                    default_storage.url(foto_perfil) if foto_perfil else ""
                )
                autenticado = True

        if autenticado:
            request.session.set_expiry(None if "lembrar" in request.POST else 0)

            if url_has_allowed_host_and_scheme(
                destino,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(destino)
            return redirect("home:index")

        contexto["erro"] = "E-mail ou senha inválidos."

    return render(request, "login.html", contexto)


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("home:index")


def cadastro_view(request):
    form = CadastroForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        nome = form.cleaned_data["nome"].strip()
        email = form.cleaned_data["email"].strip().lower()
        senha = form.cleaned_data["senha"]
        email_key = f"usuario:email:{email}"
        usuario_existente_id = redis_conn.get(email_key)

        if usuario_existente_id and redis_conn.exists(
            f"usuario:{usuario_existente_id}"
        ):
            form.add_error("email", "E-mail já cadastrado.")
        else:
            if usuario_existente_id:
                redis_conn.delete(email_key)

            usuario_id = str(uuid4())
            redis_conn.hset(
                f"usuario:{usuario_id}",
                mapping={
                    "id": usuario_id,
                    "nome": nome,
                    "email": email,
                    "senha": make_password(senha),
                },
            )
            redis_conn.set(email_key, usuario_id)
            request.session["cadastro_sucesso"] = True
            return redirect("usuarios:login")

    erros = [
        str(erro)
        for erros_campo in form.errors.values()
        for erro in erros_campo
    ]
    return render(
        request,
        "cadastro.html",
        {
            "form": form,
            "erros": erros,
            "nome": form.data.get("nome", ""),
            "email": form.data.get("email", ""),
        },
    )
    
def perfil_view(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("usuarios:login")

    usuario = redis_conn.hgetall(f"usuario:{usuario_id}")
    if not usuario:
        return redirect("usuarios:login")

    if usuario.get("foto_perfil"):
        usuario["foto_perfil_url"] = default_storage.url(usuario["foto_perfil"])

    if request.method == "POST":
        acao = request.POST.get("acao")
        erro = ""

        if acao == "editar_email":
            try:
                novo_email = (
                    EmailField()
                    .clean(request.POST.get("email", ""))
                    .strip()
                    .lower()
                )
            except ValidationError:
                erro = "Informe um endereço de e-mail válido."
            else:
                nova_chave = f"usuario:email:{novo_email}"
                usuario_existente_id = redis_conn.get(nova_chave)
                if (
                    usuario_existente_id
                    and usuario_existente_id != usuario_id
                    and redis_conn.exists(f"usuario:{usuario_existente_id}")
                ):
                    erro = "Este e-mail já está sendo usado por outra conta."
                else:
                    email_atual = usuario.get("email", "").strip().lower()
                    if email_atual != novo_email:
                        chave_atual = f"usuario:email:{email_atual}"
                        if redis_conn.get(chave_atual) == usuario_id:
                            redis_conn.delete(chave_atual)
                        redis_conn.set(nova_chave, usuario_id)
                        redis_conn.hset(f"usuario:{usuario_id}", "email", novo_email)
                        request.session["usuario_email"] = novo_email
                    return redirect("usuarios:perfil")

        elif acao == "editar_senha":
            senha_atual = request.POST.get("senha_atual", "")
            nova_senha = request.POST.get("nova_senha", "")
            confirmar_senha = request.POST.get("confirmar_senha", "")
            if not check_password(senha_atual, usuario.get("senha", "")):
                erro = "A senha atual está incorreta."
            elif len(nova_senha) < 8:
                erro = "A nova senha precisa ter pelo menos 8 caracteres."
            elif nova_senha != confirmar_senha:
                erro = "As novas senhas não coincidem."
            else:
                redis_conn.hset(
                    f"usuario:{usuario_id}", "senha", make_password(nova_senha)
                )
                return redirect("usuarios:perfil")

        elif acao == "excluir_conta":
            senha_atual = request.POST.get("senha_atual", "")
            if not check_password(senha_atual, usuario.get("senha", "")):
                erro = "A senha atual está incorreta."
            elif request.POST.get("confirmacao", "").strip() != "EXCLUIR":
                erro = "Digite EXCLUIR para confirmar a exclusão da conta."
            else:
                email_key = f"usuario:email:{usuario.get('email', '').strip().lower()}"
                if redis_conn.get(email_key) == usuario_id:
                    redis_conn.delete(email_key)
                redis_conn.delete(f"usuario:{usuario_id}")
                if usuario.get("foto_perfil"):
                    default_storage.delete(usuario["foto_perfil"])
                request.session.flush()
                return redirect("home:index")
        else:
            erro = "Não foi possível processar esta solicitação."

        return render(
            request,
            "perfil.html",
            {"usuario": usuario, "modal_aberto": acao, "modal_erro": erro},
        )

    return render(request, "perfil.html", {"usuario": usuario})


@require_http_methods(["GET", "POST"])
def personalização_perfil(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("usuarios:login")

    usuario = redis_conn.hgetall(f"usuario:{usuario_id}")
    if not usuario:
        return redirect("usuarios:login")

    form = PersonalizacaoPerfilForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        initial={"nome": usuario.get("nome", "")},
    )

    if request.method == "POST" and form.is_valid():
        foto = form.cleaned_data["foto"]
        atualizacoes = {"nome": form.cleaned_data["nome"]}
        nova_foto = None

        if foto:
            formato = getattr(getattr(foto, "image", None), "format", "") or ""
            extensao = "".join(
                caractere for caractere in formato.lower() if caractere.isalnum()
            ) or "img"
            nome_arquivo = slugify(form.cleaned_data["nome"]) or "usuario"
            nova_foto = default_storage.save(
                f"perfis/{usuario_id}/{nome_arquivo}-{usuario_id}-{uuid4().hex}.{extensao}",
                foto,
            )
            atualizacoes["foto_perfil"] = nova_foto

        redis_conn.hset(f"usuario:{usuario_id}", mapping=atualizacoes)
        request.session["usuario_nome"] = atualizacoes["nome"]
        if nova_foto:
            request.session["usuario_foto_perfil"] = default_storage.url(nova_foto)

        foto_anterior = usuario.get("foto_perfil")
        if nova_foto and foto_anterior:
            default_storage.delete(foto_anterior)

        return redirect("usuarios:perfil")

    return render(
        request,
        "configuracoes/perfil.html",
        {"usuario": usuario, "form": form},
    )


def delete_perfil(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("usuarios:login")

    usuario = redis_conn.hgetall(f"usuario:{usuario_id}")
    if not usuario:
        return redirect("usuarios:login")

    foto_perfil = usuario.get("foto_perfil")
    if foto_perfil:
        default_storage.delete(foto_perfil)

    redis_conn.delete(f"usuario:{usuario_id}")
    redis_conn.delete(f"usuario:email:{usuario.get('email', '')}")

    auth_logout(request)
    return redirect("home:index")

def seguranca_perfil(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("usuarios:login")

    usuario = redis_conn.hgetall(f"usuario:{usuario_id}")
    if not usuario:
        return redirect("usuarios:login")

    if request.method == "POST":
        acao = request.POST.get("acao")
        erro = ""

        if acao == "editar_email":
            try:
                novo_email = (
                    EmailField()
                    .clean(request.POST.get("email", ""))
                    .strip()
                    .lower()
                )
            except ValidationError:
                erro = "Informe um endereço de e-mail válido."
            else:
                nova_chave = f"usuario:email:{novo_email}"
                usuario_existente_id = redis_conn.get(nova_chave)
                if (
                    usuario_existente_id
                    and usuario_existente_id != usuario_id
                    and redis_conn.exists(f"usuario:{usuario_existente_id}")
                ):
                    erro = "Este e-mail já está sendo usado por outra conta."
                else:
                    email_atual = usuario.get("email", "").strip().lower()
                    if email_atual != novo_email:
                        chave_atual = f"usuario:email:{email_atual}"
                        if redis_conn.get(chave_atual) == usuario_id:
                            redis_conn.delete(chave_atual)
                        redis_conn.set(nova_chave, usuario_id)
                        redis_conn.hset(f"usuario:{usuario_id}", "email", novo_email)
                        request.session["usuario_email"] = novo_email
                    return redirect("usuarios:seguranca_perfil")

        elif acao == "editar_senha":
            senha_atual = request.POST.get("senha_atual", "")
            nova_senha = request.POST.get("nova_senha", "")
            confirmar_senha = request.POST.get("confirmar_senha", "")
            if not check_password(senha_atual, usuario.get("senha", "")):
                erro = "A senha atual está incorreta."
            elif len(nova_senha) < 8:
                erro = "A nova senha precisa ter pelo menos 8 caracteres."
            elif nova_senha != confirmar_senha:
                erro = "As novas senhas não coincidem."
            else:
                redis_conn.hset(
                    f"usuario:{usuario_id}", "senha", make_password(nova_senha)
                )
                return redirect("usuarios:seguranca_perfil")

        elif acao == "excluir_conta":
            senha_atual = request.POST.get("senha_atual", "")
            if not check_password(senha_atual, usuario.get("senha", "")):
                erro = "A senha atual está incorreta."
            elif request.POST.get("confirmacao", "").strip() != "EXCLUIR":
                erro = "Digite EXCLUIR para confirmar a exclusão da conta."
            else:
                email_key = f"usuario:email:{usuario.get('email', '').strip().lower()}"
                if redis_conn.get(email_key) == usuario_id:
                    redis_conn.delete(email_key)
                redis_conn.delete(f"usuario:{usuario_id}")
                if usuario.get("foto_perfil"):
                    default_storage.delete(usuario["foto_perfil"])
                request.session.flush()
                return redirect("home:index")

        else:
            erro = "Não foi possível processar esta solicitação."

        return render(
            request,
            "configuracoes/seguranca.html",
            {"usuario": usuario, "modal_aberto": acao, "modal_erro": erro},
        )

    return render(request, "configuracoes/seguranca.html", {"usuario": usuario})