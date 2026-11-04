from django.db import models
import uuid

from config.redis_conn import redis_conn


class Jogo(models.Model):
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
            "data_lancamento": data_lancamento.isoformat(),
            "status": status,
        }
        redis_conn.hset(
            f"jogo:{jogo_id}",
            mapping=dados
        )
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
            "data_lancamento": data_lancamento.isoformat(),
            "status": status,
        }
        if imagem:
            dados["imagem"] = imagem

        redis_conn.hset(f"jogo:{jogo_id}", mapping=dados)