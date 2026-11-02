import uuid

from django.contrib.auth import authenticate, get_user_model, login as auth_login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect("home:index")

    contexto = {"nome": "", "email": "", "erros": []}

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        email = request.POST.get("email", "").strip()
        senha = request.POST.get("senha", "")
        confirmar_senha = request.POST.get("confirmar_senha", "")
        contexto.update({"nome": nome, "email": email})
        erros = contexto["erros"]

        if not nome:
            erros.append("Informe seu nome.")
        if not email:
            erros.append("Informe seu e-mail.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                erros.append("Informe um e-mail válido.")

        usuario_model = get_user_model()
        if email and usuario_model.objects.filter(email__iexact=email).exists():
            erros.append("Já existe uma conta cadastrada com esse e-mail.")
        if not senha:
            erros.append("Informe uma senha.")
        elif senha != confirmar_senha:
            erros.append("As senhas não conferem.")

        if not erros and nome and email and senha:
            campos_usuario = {
                usuario_model.USERNAME_FIELD: (
                    email if usuario_model.USERNAME_FIELD == "email" else uuid.uuid4().hex
                ),
                "email": email,
                "password": senha,
            }
            if any(field.name == "first_name" for field in usuario_model._meta.fields):
                campos_usuario["first_name"] = nome
            usuario = usuario_model(**{
                key: value
                for key, value in campos_usuario.items()
                if key != "password"
            })
            try:
                validate_password(senha, user=usuario)
            except ValidationError as erro_senha:
                erros.extend(erro_senha.messages)

            if not erros:
                usuario = usuario_model.objects.create_user(**campos_usuario)
                auth_login(
                    request,
                    usuario,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                return redirect("home:index")

    return render(request, "cadastro.html", contexto)


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home:index")

    contexto = {
        "email": "",
        "erro": "",
        "next": request.GET.get("next", ""),
    }

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        senha = request.POST.get("senha", "")
        contexto["email"] = email
        contexto["next"] = request.POST.get("next", "")

        usuario_model = get_user_model()
        usuarios = list(usuario_model.objects.filter(email__iexact=email)[:2])
        usuario = None
        if email and senha and len(usuarios) == 1:
            usuario = authenticate(
                request,
                **{
                    usuario_model.USERNAME_FIELD: usuarios[0].get_username(),
                    "password": senha,
                },
            )

        if usuario is not None:
            auth_login(request, usuario)
            request.session.set_expiry(None if "lembrar" in request.POST else 0)
            destino = contexto["next"]
            if url_has_allowed_host_and_scheme(
                destino,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(destino)
            return redirect("home:index")

        contexto["erro"] = "E-mail ou senha inválidos."

    return render(request, "login.html", contexto)
