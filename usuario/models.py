from django.db import models
import uuid
from django.conf import settings
from django.contrib.auth.hashers import make_password


class Usuario:

    @staticmethod
    def criar(nome, email, senha, nome_usuario):

        redis = settings.REDIS_CLIENT

        usuario_id = str(uuid.uuid4())

        dados = {
            "id": usuario_id,
            "nome": nome,
            "email": email,
            "senha": make_password(senha),
            "nome_usuario": nome_usuario,
            "foto_perfil": ""
        }

        redis.hset(
            f"usuario:{usuario_id}",
            mapping=dados
        )

        redis.set(f"usuario:email:{email}", usuario_id)

        return usuario_id