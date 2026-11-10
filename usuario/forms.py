from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password


class CadastroForm(forms.Form):
    nome = forms.CharField(
        max_length=100,
        label="Nome",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "name",
                "placeholder": "Como podemos te chamar?",
            }
        ),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "voce@exemplo.com",
            }
        ),
    )
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Crie uma senha segura",
            }
        ),
        min_length=8,
    )
    confirmar_senha = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Digite a senha novamente",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "flex h-11 w-full rounded-md border border-input bg-background "
                "px-3 py-2 text-sm text-foreground shadow-sm transition-colors "
                "placeholder:text-muted-foreground focus-visible:outline-none "
                "focus-visible:ring-1 focus-visible:ring-ring "
                "disabled:cursor-not-allowed disabled:opacity-50"
            )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta cadastrada")
        return email

    def clean(self):
        dados = super().clean()

        senha = dados.get("senha")
        confirmar_senha = dados.get("confirmar_senha")

        if senha and confirmar_senha and senha != confirmar_senha:
            raise forms.ValidationError("As senhas não conferem.")

        if senha:
            try:
                validate_password(senha)
            except forms.ValidationError as exc:
                self.add_error("senha", exc)

        return dados

class PersonalizacaoPerfilForm(forms.Form):
    nome = forms.CharField(
        max_length=100,
        label="Nome",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "name",
                "placeholder": "Como podemos te chamar?",
            }
        ),
    )
    foto = forms.ImageField(
        label="Foto de perfil",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/*",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "flex h-11 w-full rounded-md border border-input bg-background "
                "px-3 py-2 text-sm text-foreground shadow-sm transition-colors "
                "placeholder:text-muted-foreground focus-visible:outline-none "
                "focus-visible:ring-1 focus-visible:ring-ring "
                "disabled:cursor-not-allowed disabled:opacity-50"
            )