import uuid

from django.utils import timezone

from config.redis_conn import redis_conn

# Chaves usadas no Redis:
#   jogo:{id}                 Hash  -> dados do jogo
#   jogos                     Set   -> ids de todos os jogos (catálogo)
#   jogo:{id}:detonados       Set   -> ids dos detonados daquele jogo
#   detonado:{id}             Hash  -> dados do detonado
#   detonado:{id}:etapas      List  -> ids das etapas, na ordem de criação
#   etapa:{id}                Hash  -> dados da etapa


# ---------- funções auxiliares ----------

def _txt(valor):
    """hset só aceita str/int/float/bytes: converte None, listas e datas."""
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return ", ".join(str(v) for v in valor)
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


def _dec(valor):
    """Se o redis_conn não usar decode_responses=True, vem bytes."""
    return valor.decode() if isinstance(valor, bytes) else valor


def _dict(dados):
    """Normaliza o retorno do hgetall. Hash vazio/inexistente vira None."""
    if not dados:
        return None
    return {_dec(k): _dec(v) for k, v in dados.items()}


def _ids(membros):
    return [_dec(m) for m in membros]


def _ler_hashes(prefixo, ids):
    """Lê vários Hashes com uma única ida ao Redis."""
    with redis_conn.pipeline() as pipe:
        for item_id in ids:
            pipe.hgetall(f"{prefixo}:{item_id}")
        resultados = pipe.execute()
    return [d for d in (_dict(r) for r in resultados) if d]


# ---------- Jogo ----------

class Jogo:
    @staticmethod
    def criar(
        titulo,
        descricao,
        genero,
        plataformas,
        desenvolvedora,
        distribuidora,
        imagem,
        data_lancamento,
        status="ativo",
    ):
        jogo_id = str(uuid.uuid4())
        dados = {
            "id": jogo_id,
            "titulo": titulo,
            "descricao": descricao,
            "genero": genero,
            "plataformas": plataformas,
            "desenvolvedora": desenvolvedora,
            "distribuidora": distribuidora,
            "imagem": imagem,
            "data_lancamento": data_lancamento,
            "status": status,
        }
        dados = {k: _txt(v) for k, v in dados.items()}

        redis_conn.hset(f"jogo:{jogo_id}", mapping=dados)
        redis_conn.sadd("jogos", jogo_id)
        return jogo_id

    @staticmethod
    def atualizar(
        jogo_id,
        titulo,
        descricao,
        genero,
        plataformas,
        desenvolvedora,
        distribuidora,
        data_lancamento,
        status,
        imagem=None,
    ):
        dados = {
            "titulo": titulo,
            "descricao": descricao,
            "genero": genero,
            "plataformas": plataformas,
            "desenvolvedora": desenvolvedora,
            "distribuidora": distribuidora,
            "data_lancamento": data_lancamento,
            "status": status,
        }
        if imagem:
            dados["imagem"] = imagem
        dados = {k: _txt(v) for k, v in dados.items()}
        redis_conn.hset(f"jogo:{jogo_id}", mapping=dados)

    @staticmethod
    def obter(jogo_id):
        return _dict(redis_conn.hgetall(f"jogo:{jogo_id}"))

    @staticmethod
    def listar():
        ids = _ids(redis_conn.smembers("jogos"))
        jogos = _ler_hashes("jogo", ids)
        return sorted(jogos, key=lambda j: j.get("titulo", "").lower())

    @staticmethod
    def excluir(jogo_id):
        # Redis não faz cascade: apaga os detonados (e etapas) antes
        for detonado_id in _ids(redis_conn.smembers(f"jogo:{jogo_id}:detonados")):
            Detonado.excluir(detonado_id)

        with redis_conn.pipeline() as pipe:
            pipe.delete(f"jogo:{jogo_id}")
            pipe.delete(f"jogo:{jogo_id}:detonados")
            pipe.srem("jogos", jogo_id)
            pipe.execute()


# ---------- Detonado ----------

class Detonado:
    @staticmethod
    def criar(
        jogo_id,
        titulo,
        descricao,
        conteudo=None,
        detonado_img="",
        autor_id="",
    ):
        detonado_id = str(uuid.uuid4())
        dados = {
            "id": detonado_id,
            "jogo_id": jogo_id,
            "titulo": titulo,
            "descricao": descricao,
            "conteudo": conteudo or descricao,
            "data_detonado": timezone.now(),
            "detonado_img": detonado_img,
            "autor_id": autor_id,
        }
        dados = {k: _txt(v) for k, v in dados.items()}

        redis_conn.hset(f"detonado:{detonado_id}", mapping=dados)
        redis_conn.sadd(f"jogo:{jogo_id}:detonados", detonado_id)
        return detonado_id

    @staticmethod
    def atualizar(detonado_id, titulo, descricao, conteudo=None, detonado_img=None):
        dados = {
            "titulo": titulo,
            "descricao": descricao,
        }
        if conteudo is not None:
            dados["conteudo"] = conteudo
        if detonado_img is not None:
            dados["detonado_img"] = detonado_img
        dados = {k: _txt(v) for k, v in dados.items()}
        redis_conn.hset(f"detonado:{detonado_id}", mapping=dados)

    @staticmethod
    def obter(detonado_id):
        """Devolve o detonado com a lista de etapas dentro da chave 'etapas'."""
        detonado = _dict(redis_conn.hgetall(f"detonado:{detonado_id}"))
        if not detonado:
            return None
        ids = _ids(redis_conn.lrange(f"detonado:{detonado_id}:etapas", 0, -1))
        etapas = _ler_hashes("etapa", ids)
        # _ler_hashes mantém a ordem dos ids, então as etapas já saem em ordem
        detonado["etapas"] = etapas
        return detonado

    @staticmethod
    def listar_por_jogo(jogo_id):
        ids = _ids(redis_conn.smembers(f"jogo:{jogo_id}:detonados"))
        detonados = _ler_hashes("detonado", ids)
        return sorted(
            detonados, key=lambda d: d.get("data_detonado", ""), reverse=True
        )

    @staticmethod
    def excluir(detonado_id):
        chave_etapas = f"detonado:{detonado_id}:etapas"
        jogo_id = redis_conn.hget(f"detonado:{detonado_id}", "jogo_id")
        etapas = _ids(redis_conn.lrange(chave_etapas, 0, -1))

        with redis_conn.pipeline() as pipe:
            for etapa_id in etapas:
                pipe.delete(f"etapa:{etapa_id}")
            pipe.delete(chave_etapas)
            pipe.delete(f"detonado:{detonado_id}")
            if jogo_id:
                pipe.srem(f"jogo:{_dec(jogo_id)}:detonados", detonado_id)
            pipe.execute()


# ---------- Etapa ----------

class Etapa:
    @staticmethod
    def criar(detonado_id, titulo, descricao, etapa_img=""):
        etapa_id = str(uuid.uuid4())
        dados = {
            "id": etapa_id,
            "detonado_id": detonado_id,
            "titulo": titulo,
            "descricao": descricao,
            "data_etapa": timezone.now(),
            "etapa_img": etapa_img,
        }
        dados = {k: _txt(v) for k, v in dados.items()}

        redis_conn.hset(f"etapa:{etapa_id}", mapping=dados)
        redis_conn.rpush(f"detonado:{detonado_id}:etapas", etapa_id)
        return etapa_id

    @staticmethod
    def atualizar(etapa_id, titulo, descricao, etapa_img=None):
        dados = {
            "titulo": _txt(titulo),
            "descricao": _txt(descricao),
        }
        if etapa_img is not None:
            dados["etapa_img"] = _txt(etapa_img)
        redis_conn.hset(f"etapa:{etapa_id}", mapping=dados)

    @staticmethod
    def obter(etapa_id):
        return _dict(redis_conn.hgetall(f"etapa:{etapa_id}"))

    @staticmethod
    def excluir(etapa_id):
        detonado_id = redis_conn.hget(f"etapa:{etapa_id}", "detonado_id")

        with redis_conn.pipeline() as pipe:
            pipe.delete(f"etapa:{etapa_id}")
            if detonado_id:
                pipe.lrem(f"detonado:{_dec(detonado_id)}:etapas", 0, etapa_id)
            pipe.execute()