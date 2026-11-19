from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from home.repositories.jogo_repository import JogoRepository
from home.services.jogo_service import cadastrar_jogo


class CadastrarJogoTests(SimpleTestCase):
    @patch("home.services.jogo_service.jogo_repository.criar")
    def test_normaliza_campos_e_delega_ao_repository(self, criar):
        jogo = {"id": "123", "titulo": "Zelda"}
        criar.return_value = jogo

        resultado = cadastrar_jogo(
            "  Zelda  ",
            "  Aventura ",
            " Uma jornada ",
            " Switch ",
        )

        self.assertEqual(resultado, jogo)
        criar.assert_called_once_with(
            {
                "titulo": "Zelda",
                "genero": "Aventura",
                "descricao": "Uma jornada",
                "plataforma": "Switch",
            }
        )

    def test_rejeita_campos_obrigatorios_vazios(self):
        dados_validos = ["Zelda", "Aventura", "Uma jornada", "Switch"]
        mensagens = [
            "O título do jogo é obrigatório.",
            "O gênero do jogo é obrigatório.",
            "A descrição do jogo é obrigatória.",
            "A plataforma do jogo é obrigatória.",
        ]

        for indice, mensagem in enumerate(mensagens):
            with self.subTest(campo=indice):
                dados = dados_validos.copy()
                dados[indice] = "   "
                with self.assertRaisesMessage(ValueError, mensagem):
                    cadastrar_jogo(*dados)


class JogoRepositoryTests(SimpleTestCase):
    @patch("home.repositories.redis.Redis.from_url")
    def test_cria_hash_e_adiciona_id_ao_indice(self, from_url):
        redis_client = MagicMock()
        pipeline = MagicMock()
        redis_client.pipeline.return_value.__enter__.return_value = pipeline
        from_url.return_value = redis_client

        repository = JogoRepository()
        jogo = repository.criar(
            {
                "titulo": "Zelda",
                "genero": "Aventura",
                "descricao": "Uma jornada",
                "plataforma": "Switch",
            }
        )

        self.assertTrue(jogo["id"])
        pipeline.hset.assert_called_once_with(f"jogo:{jogo['id']}", mapping=jogo)
        pipeline.sadd.assert_called_once_with("jogos:ids", jogo["id"])
        pipeline.execute.assert_called_once_with()
