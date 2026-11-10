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
    def test_busca_por_jogo_tambem_encontra_detonado_relacionado(self, redis):
        jogos = {
            "jogo:game-123": {
                "id": "game-123",
                "titulo": "The Legend of Zelda",
                "descricao": "Aventura",
                "imagem": "jogos/zelda.jpg",
            },
            "jogo:game-456": {
                "id": "game-456",
                "titulo": "Uncharted",
                "descricao": "Aventura",
                "imagem": "",
            },
        }
        detonados = {
            "detonado:guide-123": {
                "id": "guide-123",
                "jogo_id": "game-123",
                "titulo": "Guia completo",
                "descricao": "**Passo a passo**",
                "conteudo": "Como explorar Hyrule",
            },
        }
        redis.scan_iter.side_effect = lambda match: {
            "jogo:*": list(jogos),
            "detonado:*": list(detonados),
        }[match]
        redis.hgetall.side_effect = {**jogos, **detonados}.get

        resposta = self.client.get(
            reverse("catalogo:index"), {"q": "zelda", "tipo": "todos"}
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "The Legend of Zelda")
        self.assertContains(resposta, "Guia completo")
        self.assertContains(resposta, 'alt="Capa de The Legend of Zelda"')
        self.assertContains(resposta, "<strong>Passo a passo</strong>", html=True)
        self.assertNotContains(resposta, "**Passo a passo**")
        self.assertNotContains(resposta, "Uncharted")

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
    def test_pagina_de_jogo_lista_seus_detonados(self, redis):
        redis.hgetall.side_effect = [
            {
                "id": "game-123",
                "titulo": "Jogo de teste",
                "descricao": "Uma aventura",
                "imagem": "",
            },
            {
                "id": "guide-123",
                "titulo": "Guia de teste",
                "conteudo": "**Passo a passo** do jogo",
                "detonado_img": "",
            },
        ]
        redis.smembers.return_value = {"guide-123"}

        resposta = self.client.get(
            reverse("catalogo:detalhes", args=["game-123"])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Detonados deste jogo")
        self.assertContains(resposta, "Guia de teste")
        self.assertContains(resposta, "<strong>Passo a passo</strong> do jogo")
        self.assertContains(
            resposta,
            reverse("catalogo:detalhes_detonado", args=["guide-123"]),
        )
        redis.smembers.assert_called_once_with("jogo:game-123:detonados")

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
    @patch("catalogo.views.Detonado.obter")
    @patch("catalogo.views.Jogo.obter")
    def test_edicao_exibe_formulario_preenchido(self, obter_jogo, obter_detonado):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        obter_jogo.return_value = {"id": "game-123", "titulo": "Jogo teste"}
        obter_detonado.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "titulo": "Guia antigo",
            "descricao": "Descrição antiga",
            "conteudo": "**Texto**",
            "autor_id": "author-123",
            "etapas": [
                {
                    "id": "stage-1",
                    "titulo": "Etapa inicial",
                    "descricao": "Descrição da etapa",
                    "etapa_img": "",
                }
            ],
        }

        resposta = self.client.get(
            reverse("catalogo:editar_detonado", args=["game-123", "guide-123"])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Editar detonado")
        self.assertContains(resposta, 'value="Guia antigo"')
        self.assertContains(resposta, "**Texto**")
        self.assertContains(resposta, 'name="conteudo"')
        self.assertContains(resposta, 'value="stage-1"')
        self.assertContains(resposta, "Etapa inicial")

    @patch("catalogo.views.Detonado.atualizar")
    @patch("catalogo.views.Detonado.obter")
    @patch("catalogo.views.Jogo.obter")
    def test_edicao_salva_dados_e_redireciona_para_detonado(
        self,
        obter_jogo,
        obter_detonado,
        atualizar,
    ):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        obter_jogo.return_value = {"id": "game-123", "titulo": "Jogo teste"}
        obter_detonado.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "titulo": "Guia antigo",
            "conteudo": "Texto antigo",
            "autor_id": "author-123",
        }

        resposta = self.client.post(
            reverse("catalogo:editar_detonado", args=["game-123", "guide-123"]),
            {
                "titulo": "Guia atualizado",
                "conteudo": "Novo **texto**",
                "etapa_id": [""],
                "etapa_titulo": ["Etapa"],
                "etapa_descricao": ["Descrição da etapa"],
            },
        )

        self.assertRedirects(
            resposta,
            reverse("catalogo:detalhes_detonado", args=["guide-123"]),
            fetch_redirect_response=False,
        )
        atualizar.assert_called_once_with(
            "guide-123",
            titulo="Guia atualizado",
            descricao="Novo **texto**",
            conteudo="Novo **texto**",
            detonado_img="",
        )

    @patch("catalogo.views.Detonado.obter")
    @patch("catalogo.views.Jogo.obter")
    def test_edicao_invalida_mostra_mensagem_sem_apagar_valores(
        self,
        obter_jogo,
        obter_detonado,
    ):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        obter_jogo.return_value = {"id": "game-123"}
        obter_detonado.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "titulo": "Guia antigo",
            "conteudo": "Texto antigo",
            "autor_id": "author-123",
        }

        resposta = self.client.post(
            reverse("catalogo:editar_detonado", args=["game-123", "guide-123"]),
            {
                "titulo": "",
                "conteudo": "Conteúdo preservado",
                "etapa_id": [""],
                "etapa_titulo": ["Etapa"],
                "etapa_descricao": ["Descrição da etapa"],
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "This field is required.")
        self.assertContains(resposta, "Conteúdo preservado")

    @patch("catalogo.views.Etapa.criar")
    @patch("catalogo.views.Etapa.atualizar")
    @patch("catalogo.views.Etapa.excluir")
    @patch("catalogo.views.Detonado.atualizar")
    @patch("catalogo.views.Detonado.obter")
    @patch("catalogo.views.Jogo.obter")
    def test_edicao_atualiza_adiciona_e_remove_etapas(
        self,
        obter_jogo,
        obter_detonado,
        atualizar_detonado,
        excluir_etapa,
        atualizar_etapa,
        criar_etapa,
    ):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        obter_jogo.return_value = {"id": "game-123", "titulo": "Jogo teste"}
        obter_detonado.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "titulo": "Guia antigo",
            "conteudo": "Introdução antiga",
            "autor_id": "author-123",
            "detonado_img": "detonados/capa-antiga.png",
            "etapas": [
                {
                    "id": "stage-1",
                    "titulo": "Etapa antiga",
                    "descricao": "Descrição antiga",
                    "etapa_img": "detonados/etapas/antiga.png",
                },
                {
                    "id": "stage-2",
                    "titulo": "Etapa removida",
                    "descricao": "Essa etapa será removida",
                    "etapa_img": "",
                },
            ],
        }

        resposta = self.client.post(
            reverse("catalogo:editar_detonado", args=["game-123", "guide-123"]),
            {
                "titulo": "Guia atualizado",
                "conteudo": "Nova introdução",
                "etapa_id": ["stage-1", ""],
                "etapa_titulo": ["Etapa atualizada", "Nova etapa"],
                "etapa_descricao": ["Descrição atualizada", "Nova descrição"],
            },
        )

        self.assertRedirects(
            resposta,
            reverse("catalogo:detalhes_detonado", args=["guide-123"]),
            fetch_redirect_response=False,
        )
        atualizar_detonado.assert_called_once_with(
            "guide-123",
            titulo="Guia atualizado",
            descricao="Nova introdução",
            conteudo="Nova introdução",
            detonado_img="detonados/capa-antiga.png",
        )
        atualizar_etapa.assert_called_once_with(
            "stage-1",
            "Etapa atualizada",
            "Descrição atualizada",
            etapa_img="detonados/etapas/antiga.png",
        )
        excluir_etapa.assert_called_once_with("stage-2")
        criar_etapa.assert_called_once_with(
            detonado_id="guide-123",
            titulo="Nova etapa",
            descricao="Nova descrição",
            etapa_img="",
        )

    @patch("catalogo.views.default_storage.delete")
    @patch("catalogo.views._salvar_imagem", return_value="detonados/etapas/nova.png")
    @patch("catalogo.views.Etapa.criar")
    @patch("catalogo.views.Etapa.atualizar")
    @patch("catalogo.views.Detonado.atualizar")
    @patch("catalogo.views.Detonado.obter")
    @patch("catalogo.views.Jogo.obter")
    def test_imagem_selecionada_atualiza_a_etapa_correta(
        self,
        obter_jogo,
        obter_detonado,
        atualizar_detonado,
        atualizar_etapa,
        criar_etapa,
        salvar_imagem,
        apagar_imagem,
    ):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        obter_jogo.return_value = {"id": "game-123"}
        obter_detonado.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "titulo": "Guia",
            "conteudo": "Introdução",
            "autor_id": "author-123",
            "etapas": [
                {
                    "id": "stage-1",
                    "titulo": "Primeira etapa",
                    "descricao": "Texto 1",
                    "etapa_img": "detonados/etapas/primeira.png",
                },
                {
                    "id": "stage-2",
                    "titulo": "Segunda etapa",
                    "descricao": "Texto 2",
                    "etapa_img": "detonados/etapas/segunda.png",
                },
            ],
        }
        imagem_bytes = BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(imagem_bytes, format="PNG")

        resposta = self.client.post(
            reverse("catalogo:editar_detonado", args=["game-123", "guide-123"]),
            {
                "titulo": "Guia",
                "conteudo": "Introdução",
                "etapa_id": ["stage-1", "stage-2"],
                "etapa_titulo": ["Primeira etapa", "Segunda etapa"],
                "etapa_descricao": ["Texto 1", "Texto 2"],
                "etapa_img_1": SimpleUploadedFile(
                    "segunda.png",
                    imagem_bytes.getvalue(),
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            [chamada.args for chamada in atualizar_etapa.call_args_list],
            [
                ("stage-1", "Primeira etapa", "Texto 1"),
                ("stage-2", "Segunda etapa", "Texto 2"),
            ],
        )
        self.assertEqual(
            [chamada.kwargs["etapa_img"] for chamada in atualizar_etapa.call_args_list],
            ["detonados/etapas/primeira.png", "detonados/etapas/nova.png"],
        )
        apagar_imagem.assert_called_once_with("detonados/etapas/segunda.png")

    def test_acoes_de_edicao_e_exclusao_ficam_no_lado_oposto_ao_voltar(self):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        with patch("catalogo.views.redis_conn") as redis:
            redis.hgetall.return_value = {
                "id": "guide-123",
                "jogo_id": "game-123",
                "titulo": "Guia de teste",
                "autor_id": "author-123",
            }
            redis.lrange.return_value = []

            resposta = self.client.get(
                reverse("catalogo:detalhes_detonado", args=["guide-123"])
            )

        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        self.assertLess(conteudo.index("Voltar ao jogo"), conteudo.index("Editar detonado"))
        self.assertLess(conteudo.index("Editar detonado"), conteudo.index("Excluir detonado"))
        self.assertContains(resposta, "modal-excluir-detonado")
        self.assertContains(resposta, "removidos permanentemente")

    @patch("catalogo.views.Detonado.excluir")
    @patch("catalogo.views.redis_conn")
    def test_autor_exclui_detonado_e_volta_para_o_jogo(self, redis, excluir):
        sessao = self.client.session
        sessao["usuario_id"] = "author-123"
        sessao.save()
        redis.hgetall.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "autor_id": "author-123",
        }
        redis.exists.return_value = True

        resposta = self.client.post(
            reverse("catalogo:excluir_detonado", args=["guide-123"])
        )

        self.assertRedirects(
            resposta,
            reverse("catalogo:detalhes", args=["game-123"]),
        )
        excluir.assert_called_once_with("guide-123")

    @patch("catalogo.views.Detonado.excluir")
    @patch("catalogo.views.redis_conn")
    def test_usuario_nao_autorizado_nao_exclui_detonado(self, redis, excluir):
        sessao = self.client.session
        sessao["usuario_id"] = "outro-usuario"
        sessao.save()
        redis.hgetall.return_value = {
            "id": "guide-123",
            "jogo_id": "game-123",
            "autor_id": "author-123",
        }

        resposta = self.client.post(
            reverse("catalogo:excluir_detonado", args=["guide-123"])
        )

        self.assertEqual(resposta.status_code, 403)
        excluir.assert_not_called()

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
        self.assertContains(resposta, 'name="etapa_img"')
        self.assertContains(resposta, "Adicionar etapa")
        self.assertContains(resposta, 'data-markdown-action="bold"')
        self.assertContains(resposta, 'data-markdown-action="italic"')
        self.assertContains(resposta, 'data-markdown-action="line"')
        self.assertContains(resposta, 'data-open-markdown-help')
        self.assertContains(resposta, 'id="ajuda-markdown"')
        self.assertContains(resposta, "Como formatar com Markdown")

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
                self.assertEqual(
                    [chamada.args for chamada in redis_model.rpush.call_args_list],
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
                redis_views.rpush.assert_not_called()

    @patch("catalogo.models.redis_conn")
    @patch("catalogo.views.redis_conn")
    def test_formulario_de_detonado_aceita_imagem_em_etapa(
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
                        "etapa_titulo": ["Primeira fase"],
                        "etapa_descricao": ["Atravesse a floresta."],
                        "etapa_img": [
                            SimpleUploadedFile(
                                "etapa.png",
                                conteudo_imagem.getvalue(),
                                content_type="image/png",
                            )
                        ],
                    },
                )

                self.assertEqual(resposta.status_code, 302)
                detonado_mapping = redis_model.hset.call_args_list[0].kwargs["mapping"]
                etapa_mapping = redis_model.hset.call_args_list[1].kwargs["mapping"]
                self.assertEqual(detonado_mapping["titulo"], "Guia de teste")
                self.assertTrue(etapa_mapping["etapa_img"].startswith("detonados/etapas/"))
                self.assertTrue(etapa_mapping["etapa_img"].endswith(".png"))
                redis_model.rpush.assert_called_once_with(
                    f"detonado:{detonado_mapping['id']}:etapas",
                    etapa_mapping["id"],
                )
                redis_views.rpush.assert_not_called()

    @patch("catalogo.views.redis_conn")
    def test_detalhes_exibe_etapas_na_ordem_salva(self, redis):
        redis.hgetall.side_effect = [
            {
                "id": "guide-123",
                "titulo": "Guia de teste",
                "conteudo": "Introdução",
                "autor_id": "author-123",
                "data_detonado": "2026-11-09T12:30:00+00:00",
            },
            {
                "titulo": "Primeira fase",
                "descricao": "**Explore** a floresta.\n\n- Pegue a chave",
            },
            {
                "titulo": "Chefe final",
                "descricao": "<script>alert(1)</script>Derrote o chefe.",
            },
            {"nome": "Pessoa Autora"},
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
        self.assertContains(resposta, "<strong>Explore</strong>")
        self.assertContains(resposta, "<ul>")
        self.assertNotContains(resposta, "<script>")
        self.assertContains(resposta, "Pessoa Autora")
        self.assertContains(resposta, "Criado em")
        self.assertContains(resposta, "Navegação rápida")
        self.assertContains(resposta, 'href="#etapa-1"')
        self.assertContains(resposta, 'id="etapa-2"')

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
                "conteudo": "**Primeiro** passo",
            },
            {"genero": "Ação", "plataformas": "PC"},
        ]

        resposta = self.client.get(reverse("catalogo:detonados"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Guia de teste")
        self.assertContains(resposta, "<strong>Primeiro</strong> passo")
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
