from uuid import uuid4

from home.repositories.redis import get_redis_client


class JogoRepository:
    def __init__(self, client=None):
        self.client = client or get_redis_client()

    def criar(self, dados):
        jogo = {"id": str(uuid4()), **dados}
        with self.client.pipeline() as pipeline:
            pipeline.hset(f"jogo:{jogo['id']}", mapping=jogo)
            pipeline.sadd("jogos:ids", jogo["id"])
            pipeline.execute()
        return jogo
