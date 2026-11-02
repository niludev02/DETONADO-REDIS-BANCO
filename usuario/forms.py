from django import forms

class CadastroForm(forms.Form):
    nome = forms.CharField(max_length=100)
    email = forms.EmailField()
    senha = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8
    )
    confirmar_senha = forms.CharField(
        widget=forms.PasswordInput
    )

    def clean(self):
        dados = super().clean()

        senha = dados.get("senha")
        confirmar_senha = dados.get("confirmar_senha")

        if senha and confirmar_senha and senha != confirmar_senha:
            raise forms.ValidationError("As senhas não coincidem.")

        return dados