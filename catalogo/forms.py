from django import forms


class JogoForm(forms.Form):
    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
    )

    titulo = forms.CharField(
        max_length=150,
        label="Título",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Nome do jogo",
                "autocomplete": "off",
            }
        ),
    )
    descricao = forms.CharField(
        label="Descrição",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Uma breve descrição do jogo",
            }
        ),
    )
    genero = forms.CharField(
        max_length=100,
        label="Gênero",
        widget=forms.TextInput(attrs={"placeholder": "Gênero do jogo"}),
    )
    plataformas = forms.CharField(
        max_length=250,
        label="Plataformas",
        help_text="Separe as plataformas por vírgula.",
        widget=forms.TextInput(
            attrs={"placeholder": "Plataformas disponíveis"}
        ),
    )
    desenvolvedora = forms.CharField(
        max_length=150,
        label="Desenvolvedora",
        widget=forms.TextInput(attrs={"placeholder": "Nome da desenvolvedora"}),
    )
    distribuidora = forms.CharField(
        max_length=150,
        label="Distribuidora",
        widget=forms.TextInput(attrs={"placeholder": "Nome da distribuidora"}),
    )
    imagem = forms.ImageField(
        label="Imagem",
        help_text="Selecione a imagem de capa do jogo.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )
    data_lancamento = forms.DateField(
        label="Data de lançamento",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    status = forms.ChoiceField(
        label="Status",
        choices=STATUS_CHOICES,
        initial="ativo",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "w-full rounded-md border border-input bg-background px-3 py-2 "
                "text-sm text-foreground shadow-sm placeholder:text-muted-foreground "
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            )

    def clean_plataformas(self):
        plataformas = self.cleaned_data["plataformas"]
        return ", ".join(
            plataforma.strip()
            for plataforma in plataformas.split(",")
            if plataforma.strip()
        )


class JogoEdicaoForm(JogoForm):
    CAMPOS_INICIAIS = (
        "titulo",
        "descricao",
        "genero",
        "plataformas",
        "desenvolvedora",
        "distribuidora",
        "data_lancamento",
        "status",
    )

    def __init__(self, *args, jogo, **kwargs):
        initial = {
            campo: jogo.get(campo, "")
            for campo in self.CAMPOS_INICIAIS
        }
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["imagem"].required = False

class DetonadoForm(forms.Form):
    titulo = forms.CharField(
        max_length=150,
        label="Título",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Título do detonado",
                "autocomplete": "off",
            }
        ),
    )
    conteudo = forms.CharField(
        label="Conteúdo",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Conteúdo do detonado",
            }
        ),
    )
    detonado_img = forms.ImageField(
        label="Imagem do Detonado",
        help_text="Selecione a imagem do detonado.",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "w-full rounded-md border border-input bg-background px-3 py-2 "
                "text-sm text-foreground shadow-sm placeholder:text-muted-foreground "
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            )
