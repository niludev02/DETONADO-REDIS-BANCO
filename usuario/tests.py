from io import BytesIO, StringIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
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
            "is_admin": "1",
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
        self.assertTrue(self.client.session["usuario_is_admin"])

    def test_logout_limpa_sessao_redis(self):
        sessao = self.client.session
        sessao["usuario_id"] = "redis-user-id"
        sessao["usuario_nome"] = "Jogador Redis"
        sessao.save()

        resposta = self.client.post(reverse("usuarios:logout"))

        self.assertRedirects(resposta, reverse("home:index"))
        self.assertNotIn("usuario_id", self.client.session)

    def test_cabecalho_indica_usuario_admin_do_redis(self):
        sessao = self.client.session
        sessao["usuario_id"] = "redis-admin-id"
        sessao["usuario_nome"] = "Admin Redis"
        sessao["usuario_is_admin"] = True
        sessao.save()

        resposta = self.client.get(reverse("home:index"))

        self.assertContains(resposta, "Administrador")


class CriarAdminRedisTests(TestCase):
    @patch(
        "usuario.management.commands.criar_admin_redis.getpass.getpass",
        side_effect=["UmaSenha-admin-987!", "UmaSenha-admin-987!"],
    )
    @patch("usuario.management.commands.criar_admin_redis.redis_conn")
    def test_comando_cria_admin_com_senha_hash(self, redis, _getpass):
        redis.get.return_value = None
        pipeline = redis.pipeline.return_value.__enter__.return_value
        saida = StringIO()

        call_command(
            "criar_admin_redis",
            nome="Admin",
            email="ADMIN@example.com",
            stdout=saida,
        )

        dados = pipeline.hset.call_args.kwargs["mapping"]
        self.assertEqual(dados["email"], "admin@example.com")
        self.assertEqual(dados["is_admin"], "1")
        self.assertTrue(
            check_password("UmaSenha-admin-987!", dados["senha"])
        )
        pipeline.set.assert_called_once_with(
            "usuario:email:admin@example.com", dados["id"]
        )
        pipeline.execute.assert_called_once()
        self.assertIn("Conta administradora criada", saida.getvalue())


class PerfilTests(TestCase):
    @patch("usuario.views.redis_conn")
    def test_perfil_exibe_dados_da_conta_redis(self, redis):
        sessao = self.client.session
        sessao["usuario_id"] = "redis-user-id"
        sessao.save()
        redis.hgetall.return_value = {
            "id": "redis-user-id",
            "nome": "Jogadora Teste",
            "email": "jogadora@example.com",
            "is_admin": "1",
        }

        resposta = self.client.get(reverse("usuarios:perfil"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Jogadora Teste")
        self.assertContains(resposta, "jogadora@example.com")
        self.assertContains(resposta, "Administrador")
        self.assertContains(resposta, reverse("usuarios:administracao_jogos"))


class AdministracaoJogosTests(TestCase):
    def setUp(self):
        sessao = self.client.session
        sessao["usuario_id"] = "redis-admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()

    @patch("usuario.views.Jogo.listar")
    def test_lista_jogos_em_tabela_com_acao_de_excluir(self, listar):
        listar.return_value = [
            {
                "id": "jogo-123",
                "titulo": "Jogo de teste",
                "genero": "Aventura",
                "plataformas": "PC",
                "status": "ativo",
                "imagem": "jogos/capa.png",
            }
        ]

        resposta = self.client.get(reverse("usuarios:administracao_jogos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "<table")
        self.assertContains(resposta, "Jogo de teste")
        self.assertContains(resposta, "Aventura")
        self.assertContains(resposta, "Plataformas")
        self.assertContains(resposta, "data-open-delete-game")
        self.assertContains(resposta, "modal-excluir-jogo")
        self.assertContains(resposta, "detonados e etapas")

    @patch("usuario.views.Jogo.excluir")
    @patch("usuario.views.Jogo.obter")
    def test_admin_exclui_jogo_pelo_post(self, obter, excluir):
        obter.return_value = {"id": "jogo-123"}

        resposta = self.client.post(
            reverse("usuarios:excluir_jogo_administracao", args=["jogo-123"])
        )

        self.assertRedirects(
            resposta,
            reverse("usuarios:administracao_jogos"),
        )
        excluir.assert_called_once_with("jogo-123")

    @patch("usuario.views.Jogo.excluir")
    @patch("usuario.views.Jogo.obter")
    def test_usuario_comum_nao_pode_excluir_jogo(self, obter, excluir):
        sessao = self.client.session
        sessao["usuario_is_admin"] = False
        sessao.save()
        obter.return_value = {"id": "jogo-123"}

        resposta = self.client.post(
            reverse("usuarios:excluir_jogo_administracao", args=["jogo-123"])
        )

        self.assertEqual(resposta.status_code, 403)
        excluir.assert_not_called()

    @patch("usuario.views.Jogo.obter", return_value=None)
    def test_exclusao_de_jogo_inexistente_retorna_404(self, obter):
        resposta = self.client.post(
            reverse("usuarios:excluir_jogo_administracao", args=["nao-existe"])
        )

        self.assertEqual(resposta.status_code, 404)


class PersonalizacaoPerfilTests(TestCase):
    def setUp(self):
        sessao = self.client.session
        sessao["usuario_id"] = "redis-user-id"
        sessao.save()
        self.usuario = {
            "id": "redis-user-id",
            "nome": "Jogadora Teste",
            "email": "jogadora@example.com",
        }
        self.url = reverse("usuarios:personalização_perfil")

    @patch("usuario.views.redis_conn")
    def test_formulario_carrega_nome_atual(self, redis):
        redis.hgetall.return_value = self.usuario

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["form"].initial["nome"], "Jogadora Teste")

    @patch("usuario.views.redis_conn")
    def test_salva_nome_validado_e_atualiza_sessao(self, redis):
        redis.hgetall.return_value = self.usuario

        resposta = self.client.post(self.url, {"nome": "Novo nome"})

        self.assertRedirects(resposta, reverse("usuarios:perfil"))
        redis.hset.assert_called_once_with(
            "usuario:redis-user-id",
            mapping={"nome": "Novo nome"},
        )
        self.assertEqual(self.client.session["usuario_nome"], "Novo nome")

    @patch("usuario.views.redis_conn")
    def test_salva_foto_enviada(self, redis):
        redis.hgetall.return_value = self.usuario
        imagem = BytesIO()
        Image.new("RGB", (1, 1), color="red").save(imagem, format="PNG")

        with TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                resposta = self.client.post(
                    self.url,
                    {
                        "nome": "Jogadora Teste",
                        "foto": SimpleUploadedFile(
                            "foto.png",
                            imagem.getvalue(),
                            content_type="image/png",
                        ),
                    },
                )

                self.assertRedirects(resposta, reverse("usuarios:perfil"))
                caminho_foto = redis.hset.call_args.kwargs["mapping"]["foto_perfil"]
                self.assertTrue(default_storage.exists(caminho_foto))
                self.assertIn("jogadora-teste-redis-user-id-", caminho_foto)
                self.assertEqual(
                    self.client.session["usuario_foto_perfil"],
                    default_storage.url(caminho_foto),
                )

    def test_cabecalho_exibe_foto_com_tamanho_fixo(self):
        sessao = self.client.session
        sessao["usuario_foto_perfil"] = "/media/perfis/redis-user-id/foto.png"
        sessao["usuario_nome"] = "Jogadora Teste"
        sessao.save()

        resposta = self.client.get(reverse("home:index"))

        self.assertContains(resposta, 'src="/media/perfis/redis-user-id/foto.png"')
        self.assertContains(resposta, "size-8 shrink-0 rounded-full object-cover")
        self.assertContains(resposta, "Jogadora Teste")
