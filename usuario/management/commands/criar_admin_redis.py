import getpass
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
import redis

from config.redis_conn import redis_conn


class Command(BaseCommand):
    help = "Cria uma conta administrativa armazenada no Redis."

    def add_arguments(self, parser):
        parser.add_argument("--nome", required=True)
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        nome = options["nome"].strip()
        email = options["email"].strip().lower()
        if not nome or not email:
            raise CommandError("Nome e e-mail são obrigatórios.")

        email_key = f"usuario:email:{email}"
        try:
            usuario_existente_id = redis_conn.get(email_key)
            if usuario_existente_id and redis_conn.exists(
                f"usuario:{usuario_existente_id}"
            ):
                raise CommandError("Já existe uma conta com esse e-mail.")

            senha = getpass.getpass("Senha do administrador: ")
            confirmacao = getpass.getpass("Confirme a senha: ")
            if senha != confirmacao:
                raise CommandError("As senhas não coincidem.")

            try:
                validate_password(senha)
            except ValidationError as error:
                raise CommandError(" ".join(error.messages)) from error

            usuario_id = str(uuid4())
            with redis_conn.pipeline() as pipeline:
                pipeline.hset(
                    f"usuario:{usuario_id}",
                    mapping={
                        "id": usuario_id,
                        "nome": nome,
                        "email": email,
                        "senha": make_password(senha),
                        "is_admin": "1",
                    },
                )
                pipeline.set(email_key, usuario_id)
                pipeline.execute()
        except redis.RedisError as error:
            raise CommandError(f"Não foi possível gravar no Redis: {error}") from error

        self.stdout.write(self.style.SUCCESS("Conta administradora criada no Redis."))