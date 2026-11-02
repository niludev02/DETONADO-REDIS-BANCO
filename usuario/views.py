
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import make_password
from uuid import uuid4

from .redis_conn import redis_conn


@require_POST
def cadastrar_usuario(request):
    form = 
    nome = request.POST.get('nome', '').strip()
    email = request.POST.get('email', '').strip().lower()
    senha = request.POST.get('senha', '')

    # Validação dos campos
    if not nome or not email or not senha:
        return JsonResponse({
            'erro': 'Preencha todos os campos.'
        }, status=400)

    # Verifica se o e-mail já está cadastrado
    email_key = f'usuario:email:{email}'

    if redis_conn.exists(email_key):
        return JsonResponse({
            'erro': 'E-mail já cadastrado.'
        }, status=409)

    # Gera identificador único
    usuario_id = str(uuid4())

    # Armazena os dados no Redis
    redis_conn.hset(
        f'usuario:{usuario_id}',
        mapping={
            'id': usuario_id,
            'nome': nome,
            'email': email,
            'senha': make_password(senha)
        }
    )

    # Cria índice para localizar usuário pelo e-mail
    redis_conn.set(email_key, usuario_id)

    return JsonResponse({
        'mensagem': 'Usuário cadastrado com sucesso!',
        'id': usuario_id
    }, status=201)
