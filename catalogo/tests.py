from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


class CriarJogoTests(TestCase):
    @patch("catalogo.views.redis_conn")
    def test_catalogo_ignora_chaves_auxiliares_de_detonados(self, redis):
        redis.scan_iter.return_value = [
            "jogo:game-123",
            "jogo:game-123:detonados",
        ]
        redis.hgetall.return_value = {
            "id": "game-123",
            "titulo": "Jogo de teste",
            "descricao": "Descrição",
            "imagem": "",
        }

        resposta = self.client.get(reverse("catalogo:index"))

        self.assertEqual(resposta.status_code, 200)
        redis.hgetall.assert_called_once_with("jogo:game-123")

    @patch("catalogo.views.redis_conn")
    def test_card_do_catalogo_abre_detalhes_do_jogo(self, redis):
        redis.scan_iter.return_value = ["jogo:game-123"]
        redis.hgetall.return_value = {
            "id": "game-123",
            "titulo": "Jogo de teste",
            "descricao": "Descrição",
            "imagem": "",
        }

        resposta = self.client.get(reverse("catalogo:index"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, reverse("catalogo:detalhes", args=["game-123"]))
        self.assertContains(resposta, "Ver detalhes de Jogo de teste")

    @patch("catalogo.views.redis_conn")
    def test_pagina_de_detalhes_exibe_informacoes_do_jogo(self, redis):
        redis.hgetall.return_value = {
            "id": "game-123",
            "titulo": "Jogo de teste",
            "descricao": "Uma aventura",
            "genero": "Ação",
            "plataformas": "PC",
            "desenvolvedora": "Estúdio",
            "distribuidora": "Publicadora",
            "data_lancamento": "2024-01-01",
            "status": "ativo",
            "imagem": "",
        }

        resposta = self.client.get(
            reverse("catalogo:detalhes", args=["game-123"])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Uma aventura")
        self.assertContains(resposta, "Desenvolvedora")
        self.assertContains(resposta, "Distribuidora")

    @patch("catalogo.views.redis_conn")
    def test_detalhes_de_jogo_inexistente_retorna_404(self, redis):
        redis.hgetall.return_value = {}

        resposta = self.client.get(
            reverse("catalogo:detalhes", args=["nao-existe"])
        )

        self.assertEqual(resposta.status_code, 404)

    @patch("catalogo.views.redis_conn")
    def test_formulario_de_edicao_exibe_dados_atuais(self, redis):
        sessao = self.client.session
        sessao["usuario_id"] = "admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()
        redis.hgetall.return_value = {
            "id": "game-123",
            "titulo": "Jogo de teste",
            "descricao": "Descrição atual",
            "genero": "Ação",
            "plataformas": "PC",
            "desenvolvedora": "Estúdio",
            "distribuidora": "Publicadora",
            "data_lancamento": "2024-01-01",
            "status": "ativo",
            "imagem": "",
        }

        resposta = self.client.get(reverse("catalogo:editar", args=["game-123"]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'value="Jogo de teste"')
        self.assertContains(resposta, 'name="descricao"')
        self.assertContains(resposta, 'value="2024-01-01"')

    @patch("catalogo.models.redis_conn")
    @patch("catalogo.views.redis_conn")
    def test_admin_edita_jogo_sem_substituir_imagem(self, redis_views, redis_model):
        sessao = self.client.session
        sessao["usuario_id"] = "admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()
        redis_views.hgetall.return_value = {
            "id": "game-123",
            "titulo": "Título antigo",
            "descricao": "Descrição antiga",
            "genero": "Ação",
            "plataformas": "PC",
            "desenvolvedora": "Estúdio",
            "distribuidora": "Publicadora",
            "data_lancamento": "2024-01-01",
            "status": "ativo",
            "imagem": "jogos/capa.png",
        }

        resposta = self.client.post(
            reverse("catalogo:editar", args=["game-123"]),
            {
                "titulo": "Título atualizado",
                "descricao": "Descrição atualizada",
                "genero": "Aventura",
                "plataformas": "PC, Switch",
                "desenvolvedora": "Estúdio novo",
                "distribuidora": "Publicadora nova",
                "data_lancamento": "2024-02-01",
                "status": "inativo",
            },
        )

        self.assertRedirects(
            resposta,
            reverse("catalogo:detalhes", args=["game-123"]),
        )
        mapping = redis_model.hset.call_args.kwargs["mapping"]
        self.assertEqual(mapping["titulo"], "Título atualizado")
        self.assertEqual(mapping["descricao"], "Descrição atualizada")
        self.assertEqual(mapping["plataformas"], "PC, Switch")
        self.assertEqual(mapping["data_lancamento"], "2024-02-01")
        self.assertEqual(mapping["status"], "inativo")
        self.assertNotIn("imagem", mapping)

    @patch("catalogo.views.redis_conn")
    def test_usuario_sem_permissao_nao_pode_editar(self, redis):
        resposta = self.client.post(reverse("catalogo:editar", args=["game-123"]))

        self.assertRedirects(resposta, reverse("usuarios:login"))
        redis.hgetall.assert_not_called()

    def test_formulario_aparece_apenas_para_admin(self):
        sessao = self.client.session
        sessao["usuario_id"] = "admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()

        with patch("catalogo.views.redis_conn") as redis:
            redis.scan_iter.return_value = []
            resposta = self.client.get(reverse("catalogo:index"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Adicionar jogo")
        self.assertContains(resposta, reverse("catalogo:criar"))
        self.assertNotContains(resposta, 'name="nome"')

    def test_formulario_fica_em_pagina_separada(self):
        sessao = self.client.session
        sessao["usuario_id"] = "admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()

        resposta = self.client.get(reverse("catalogo:criar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Cadastrar jogo")
        self.assertContains(resposta, 'name="titulo"')
        self.assertContains(resposta, 'name="descricao"')
        self.assertContains(resposta, 'name="genero"')
        self.assertContains(resposta, 'name="plataformas"')
        self.assertContains(resposta, 'name="desenvolvedora"')
        self.assertContains(resposta, 'name="distribuidora"')
        self.assertContains(resposta, 'name="imagem"')
        self.assertContains(resposta, 'type="file"')
        self.assertContains(resposta, 'enctype="multipart/form-data"')
        self.assertContains(resposta, 'name="data_lancamento"')
        self.assertContains(resposta, 'name="status"')

    @patch("catalogo.models.redis_conn")
    def test_admin_cadastra_jogo_no_redis(self, redis):
        sessao = self.client.session
        sessao["usuario_id"] = "admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()

        conteudo_imagem = BytesIO()
        Image.new("RGB", (1, 1), color="red").save(conteudo_imagem, format="PNG")

        with TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                resposta = self.client.post(
                    reverse("catalogo:criar"),
                    {
                        "titulo": "Hollow Knight",
                        "descricao": "Descrição do jogo",
                        "genero": "Metroidvania",
                        "plataformas": "PC, Nintendo Switch",
                        "desenvolvedora": "Team Cherry",
                        "distribuidora": "Team Cherry",
                        "imagem": SimpleUploadedFile(
                            "capa.png",
                            conteudo_imagem.getvalue(),
                            content_type="image/png",
                        ),
                        "data_lancamento": "2017-02-24",
                        "status": "ativo",
                    },
                )

                self.assertRedirects(resposta, reverse("catalogo:index"))
                mapping = redis.hset.call_args.kwargs["mapping"]
                self.assertEqual(mapping["titulo"], "Hollow Knight")
                self.assertEqual(mapping["descricao"], "Descrição do jogo")
                self.assertEqual(mapping["genero"], "Metroidvania")
                self.assertEqual(mapping["plataformas"], "PC, Nintendo Switch")
                self.assertEqual(mapping["desenvolvedora"], "Team Cherry")
                self.assertEqual(mapping["distribuidora"], "Team Cherry")
                self.assertTrue(mapping["imagem"].startswith("jogos/"))
                self.assertTrue(mapping["imagem"].endswith(".png"))
                self.assertTrue(default_storage.exists(mapping["imagem"]))
                self.assertEqual(mapping["data_lancamento"], "2017-02-24")
                self.assertEqual(mapping["status"], "ativo")
                self.assertTrue(mapping["id"])
                redis.hset.assert_called_once()

    def test_usuario_sem_permissao_nao_pode_cadastrar(self):
        resposta = self.client.post(
            reverse("catalogo:criar"),
            {
                "titulo": "Jogo de teste",
                "descricao": "Descrição",
                "genero": "Ação",
                "plataformas": "PC",
                "desenvolvedora": "Estúdio",
                "distribuidora": "Estúdio",
                "data_lancamento": "2024-01-01",
            },
        )

        self.assertRedirects(resposta, reverse("usuarios:login"))

    @patch("catalogo.views.redis_conn")
    def test_usuario_logado_nao_admin_recebe_proibido(self, redis):
        sessao = self.client.session
        sessao["usuario_id"] = "membro-id"
        sessao["usuario_is_admin"] = False
        sessao.save()

        resposta = self.client.post(reverse("catalogo:criar"))

        self.assertEqual(resposta.status_code, 403)
        redis.scan_iter.assert_not_called()


class DetonadosTests(TestCase):
    @patch("catalogo.views.redis_conn")
    def test_formulario_de_detonado_exibe_campos(self, redis):
        redis.hgetall.return_value = {"id": "game-123", "titulo": "Jogo de teste"}

        resposta = self.client.get(
            reverse("catalogo:criar_detonado", args=["game-123"])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'name="titulo"')
        self.assertContains(resposta, 'name="conteudo"')
        self.assertContains(resposta, 'name="detonado_img"')
        self.assertContains(resposta, 'name="etapa_titulo"')
        self.assertContains(resposta, 'name="etapa_descricao"')
        self.assertContains(resposta, "Adicionar etapa")

    @patch("catalogo.models.redis_conn")
    @patch("catalogo.views.redis_conn")
    def test_formulario_valido_salva_detonado_e_redireciona(
        self,
        redis_views,
        redis_model,
    ):
        redis_views.hgetall.return_value = {"id": "game-123", "titulo": "Jogo de teste"}
        conteudo_imagem = BytesIO()
        Image.new("RGB", (1, 1), color="red").save(conteudo_imagem, format="PNG")

        with TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                resposta = self.client.post(
                    reverse("catalogo:criar_detonado", args=["game-123"]),
                    {
                        "titulo": "Guia de teste",
                        "conteudo": "Passo a passo",
                        "etapa_titulo": ["Primeira fase", "Chefe final"],
                        "etapa_descricao": [
                            "Atravesse a floresta.",
                            "Derrote o chefe.",
                        ],
                        "detonado_img": SimpleUploadedFile(
                            "guia.png",
                            conteudo_imagem.getvalue(),
                            content_type="image/png",
                        ),
                    },
                )

                self.assertRedirects(
                    resposta,
                    reverse(
                        "catalogo:detalhes_detonado",
                        args=[
                            redis_model.hset.call_args_list[0]
                            .args[0]
                            .split(":", 1)[1]
                        ],
                    ),
                )

                detonado_mapping = redis_model.hset.call_args_list[0].kwargs["mapping"]
                etapa_mapping = [
                    chamada.kwargs["mapping"]
                    for chamada in redis_model.hset.call_args_list[1:]
                ]
                self.assertEqual(detonado_mapping["titulo"], "Guia de teste")
                self.assertEqual(detonado_mapping["conteudo"], "Passo a passo")
                self.assertTrue(
                    detonado_mapping["detonado_img"].startswith("detonados/")
                )
                self.assertEqual(
                    [etapa["titulo"] for etapa in etapa_mapping],
                    ["Primeira fase", "Chefe final"],
                )
                self.assertEqual(
                    [etapa["descricao"] for etapa in etapa_mapping],
                    ["Atravesse a floresta.", "Derrote o chefe."],
                )
                redis_views.sadd.assert_any_call(
                    "jogo:game-123:detonados",
                    detonado_mapping["id"],
                )
                self.assertEqual(redis_views.sadd.call_count, 1)
                self.assertEqual(
                    [chamada.args for chamada in redis_views.rpush.call_args_list],
                    [
                        (
                            f"detonado:{detonado_mapping['id']}:etapas",
                            etapa_mapping[0]["id"],
                        ),
                        (
                            f"detonado:{detonado_mapping['id']}:etapas",
                            etapa_mapping[1]["id"],
                        ),
                    ],
                )

    @patch("catalogo.views.redis_conn")
    def test_detalhes_exibe_etapas_na_ordem_salva(self, redis):
        redis.hgetall.side_effect = [
            {
                "id": "guide-123",
                "titulo": "Guia de teste",
                "conteudo": "Introdução",
            },
            {"titulo": "Primeira fase", "descricao": "Explore a floresta."},
            {"titulo": "Chefe final", "descricao": "Derrote o chefe."},
        ]
        redis.lrange.return_value = ["stage-1", "stage-2"]

        resposta = self.client.get(
            reverse("catalogo:detalhes_detonado", args=["guide-123"])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertLess(
            resposta.content.index(b"Primeira fase"),
            resposta.content.index(b"Chefe final"),
        )

    @patch("catalogo.models.redis_conn")
    @patch("catalogo.views.redis_conn")
    def test_etapa_incompleta_nao_salva_detonado(
        self,
        redis_views,
        redis_model,
    ):
        redis_views.hgetall.return_value = {"id": "game-123", "titulo": "Jogo de teste"}
        conteudo_imagem = BytesIO()
        Image.new("RGB", (1, 1), color="red").save(conteudo_imagem, format="PNG")

        resposta = self.client.post(
            reverse("catalogo:criar_detonado", args=["game-123"]),
            {
                "titulo": "Guia de teste",
                "conteudo": "Passo a passo",
                "etapa_titulo": ["Primeira fase"],
                "etapa_descricao": [""],
                "detonado_img": SimpleUploadedFile(
                    "guia.png",
                    conteudo_imagem.getvalue(),
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Preencha o título e a descrição da etapa.")
        redis_model.hset.assert_not_called()
        redis_views.sadd.assert_not_called()

    @patch("catalogo.views.redis_conn")
    def test_lista_global_de_detonados_abre(self, redis):
        redis.scan_iter.return_value = []

        resposta = self.client.get(reverse("catalogo:detonados"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Nenhum detonado encontrado")
        redis.scan_iter.assert_called_once_with(match="detonado:*")

    def test_botao_ver_detonados_da_home_abre_a_lista(self):
        resposta = self.client.get(reverse("home:index"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, reverse("catalogo:detonados"))

    @patch("catalogo.views.redis_conn")
    def test_admin_consegue_abrir_lista_global_sem_erro_de_url(self, redis):
        sessao = self.client.session
        sessao["usuario_id"] = "admin-id"
        sessao["usuario_is_admin"] = True
        sessao.save()
        redis.scan_iter.return_value = []

        resposta = self.client.get(reverse("catalogo:detonados"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, reverse("catalogo:index"))
        self.assertContains(resposta, "Escolher um jogo")

    @patch("catalogo.views.redis_conn")
    def test_lista_global_exibe_detonado_e_link_para_detalhes(self, redis):
        redis.scan_iter.return_value = ["detonado:guide-123"]
        redis.hgetall.side_effect = [
            {
                "id": "guide-123",
                "jogo_id": "game-123",
                "titulo": "Guia de teste",
                "conteudo": "Primeiro passo",
            },
            {"genero": "Ação", "plataformas": "PC"},
        ]

        resposta = self.client.get(reverse("catalogo:detonados"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Guia de teste")
        self.assertContains(resposta, "Primeiro passo")
        self.assertContains(
            resposta,
            reverse("catalogo:detalhes_detonado", args=["guide-123"]),
        )

    @patch("catalogo.views.redis_conn")
    def test_lista_ignora_chaves_de_etapas_do_detonado(self, redis):
        redis.scan_iter.return_value = [
            "detonado:guide-123",
            "detonado:guide-123:etapas",
        ]
        redis.hgetall.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "titulo": "Guia de teste",
            "conteudo": "Primeiro passo",
        }

        resposta = self.client.get(reverse("catalogo:detonados"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(redis.hgetall.call_count, 2)

    @patch("catalogo.views.redis_conn")
    def test_detalhes_de_detonado_sem_imagem_abre(self, redis):
        redis.hgetall.return_value = {
            "id": "guide-123",
            "titulo": "Guia de teste",
            "conteudo": "Primeiro passo",
        }

        resposta = self.client.get(
            reverse("catalogo:detalhes_detonado", args=["guide-123"])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Primeiro passo")
        self.assertNotContains(resposta, "Imagem do Detonado")
