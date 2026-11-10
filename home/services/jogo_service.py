from home.repositories.jogo_repository import JogoRepository


jogo_repository = JogoRepository()


def cadastrar_jogo(titulo, genero, descricao, plataforma):
    campos = [
        (titulo, "O título do jogo é obrigatório."),
        (genero, "O gênero do jogo é obrigatório."),
        (descricao, "A descrição do jogo é obrigatória."),
        (plataforma, "A plataforma do jogo é obrigatória."),
    ]

    for valor, mensagem in campos:
        if valor is None or not str(valor).strip():
            raise ValueError(mensagem)

    dados = {
        "titulo": str(titulo).strip(),
        "genero": str(genero).strip(),
        "descricao": str(descricao).strip(),
        "plataforma": str(plataforma).strip(),
    }

    return jogo_repository.criar(dados)
