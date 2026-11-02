
from django.contrib.auth import authenticate, get_user_model, login as auth_login
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from uuid import uuid4

from .forms import CadastroForm
from config.redis_conn import redis_conn


@require_http_methods(["GET", "POST"])
def login_view(request):
    contexto = {
        "email": "",
        "erro": "",
        "next": request.GET.get("next", ""),
    }

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


def cadastro_view(request):
    form = CadastroForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        nome = form.cleaned_data["nome"].strip()
        email = form.cleaned_data["email"].strip().lower()
        senha = form.cleaned_data["senha"]
        email_key = f"usuario:email:{email}"

        if redis_conn.exists(email_key):
            form.add_error("email", "E-mail já cadastrado.")
        else:
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
