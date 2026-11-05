from django.db import models
from django.utils import timezone
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

class Detonado(models.Model):
    @staticmethod
    def criar(
        jogo_id,
        titulo,
        descricao,
        conteudo=None,
        detonado_img="",
    ):
        detonado_id = str(uuid.uuid4())
        dados = {
            "id": detonado_id,
            "jogo_id": jogo_id,
            "titulo": titulo,
            "descricao": descricao,
            "conteudo": conteudo or descricao,
            "data_detonado": timezone.now().isoformat(),
            "detonado_img": detonado_img,
        }
        redis_conn.hset(f"detonado:{detonado_id}", mapping=dados)
        return detonado_id

    @staticmethod
    def atualizar(detonado_id, titulo, descricao):
        dados = {
            "titulo": titulo,
            "descricao": descricao,
        }                   
        redis_conn.hset(f"detonado:{detonado_id}", mapping=dados)
        
class Etapa(models.Model):
    @staticmethod
    def criar(detonado_id, titulo, descricao):
        etapa_id = str(uuid.uuid4())
        dados = {
            "id": etapa_id,
            "detonado_id": detonado_id,
            "titulo": titulo,
            "descricao": descricao,
            "data_etapa": timezone.now().isoformat(),
            "etapa_img": ""
        }
        redis_conn.hset(f"etapa:{etapa_id}", mapping=dados)
        return etapa_id

    @staticmethod
    def atualizar(etapa_id, titulo, descricao):
        dados = {
            "titulo": titulo,
            "descricao": descricao,
        }
        redis_conn.hset(f"etapa:{etapa_id}", mapping=dados)