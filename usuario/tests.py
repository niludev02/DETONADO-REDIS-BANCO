from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from unittest.mock import patch


class CadastroTests(TestCase):
    def setUp(self):
        self.url = reverse("usuarios:cadastro")
        self.dados_validos = {
            "nome": "Jogador Novo",
            "email": "novo@example.com",
            "senha": "UmaSenha-forte-987!",
            "confirmar_senha": "UmaSenha-forte-987!",
        }

    def test_exibe_tela_de_cadastro(self):
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Criar minha conta")
        self.assertContains(resposta, 'name="confirmar_senha"')

    def test_cadastro_cria_conta_com_senha_hash_e_autentica(self):
        resposta = self.client.post(self.url, self.dados_validos)

        usuario = get_user_model().objects.get(email="novo@example.com")
        self.assertRedirects(resposta, reverse("home:index"))
        self.assertTrue(usuario.check_password(self.dados_validos["senha"]))
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_rejeita_email_duplicado_ignorando_maiusculas(self):
        get_user_model().objects.create_user(
            username="jogador-existente",
            email="novo@example.com",
            password="Senha-segura-123!",
        )

        resposta = self.client.post(
            self.url,
            {**self.dados_validos, "email": "NOVO@example.com"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe uma conta cadastrada")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_rejeita_senhas_diferentes(self):
        resposta = self.client.post(
            self.url,
            {**self.dados_validos, "confirmar_senha": "outra-senha"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "As senhas não conferem.")
        self.assertFalse(
            get_user_model().objects.filter(email="novo@example.com").exists()
        )

    def test_rejeita_senha_fraca(self):
        resposta = self.client.post(
            self.url,
            {
                **self.dados_validos,
                "senha": "password",
                "confirmar_senha": "password",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "senha")
        self.assertFalse(
            get_user_model().objects.filter(email="novo@example.com").exists()
        )


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="jogador",
            email="jogador@example.com",
            password="senha-segura-123",
        )
        self.url = reverse("usuarios:login")

    def test_exibe_tela_de_login(self):
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Acesse sua conta")
        self.assertContains(resposta, 'name="email"')

    def test_login_com_credenciais_validas(self):
        resposta = self.client.post(
            self.url,
            {"email": self.usuario.email, "senha": "senha-segura-123"},
        )

        self.assertRedirects(resposta, reverse("home:index"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)

    def test_login_invalido_mostra_erro(self):
        resposta = self.client.post(
            self.url,
            {"email": self.usuario.email, "senha": "senha-incorreta"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "E-mail ou senha inválidos.")

    def test_nao_autentica_email_duplicado(self):
        get_user_model().objects.create_user(
            username="outro-jogador",
            email=self.usuario.email,
            password="outra-senha-segura",
        )

        resposta = self.client.post(
            self.url,
            {"email": self.usuario.email, "senha": "senha-segura-123"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "E-mail ou senha inválidos.")

    @patch("usuario.views.redis_conn")
    def test_login_com_conta_redis(self, redis):
        redis.get.return_value = "redis-user-id"
        redis.hgetall.return_value = {
            "id": "redis-user-id",
            "nome": "Jogador Redis",
            "email": "redis@example.com",
            "senha": make_password("senha-redis-segura"),
        }

        resposta = self.client.post(
            self.url,
            {"email": "redis@example.com", "senha": "senha-redis-segura"},
        )

        self.assertRedirects(resposta, reverse("home:index"))
        self.assertEqual(self.client.session["usuario_id"], "redis-user-id")
        self.assertEqual(
            self.client.session["usuario_nome"], "Jogador Redis"
        )

    def test_logout_limpa_sessao_redis(self):
        sessao = self.client.session
        sessao["usuario_id"] = "redis-user-id"
        sessao["usuario_nome"] = "Jogador Redis"
        sessao.save()

        resposta = self.client.post(reverse("usuarios:logout"))

        self.assertRedirects(resposta, reverse("home:index"))
        self.assertNotIn("usuario_id", self.client.session)
