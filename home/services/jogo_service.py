from home.repositories.jogo_repository import jogo_repository


def cadastrar_jogo(
    titulo: str,
    genero: str,
    descricao: str,
    plataforma: str,
) -> dict[str, str]:
    campos = {
        "titulo": titulo,
        "genero": genero,
        "descricao": descricao,
        "plataforma": plataforma,
    }
    mensagens = {
        "titulo": "O título do jogo é obrigatório.",
        "genero": "O gênero do jogo é obrigatório.",
        "descricao": "A descrição do jogo é obrigatória.",
        "plataforma": "A plataforma do jogo é obrigatória.",
    }

    for campo, valor in campos.items():
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(mensagens[campo])

    dados = {campo: valor.strip() for campo, valor in campos.items()}
    return jogo_repository.criar(dados)
