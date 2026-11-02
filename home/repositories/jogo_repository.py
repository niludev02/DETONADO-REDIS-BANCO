import os
from uuid import uuid4

import redis


class JogoRepository:
    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )

    def criar(self, dados: dict[str, str]) -> dict[str, str]:
        jogo = {"id": uuid4().hex, **dados}
        jogo_key = f"jogo:{jogo['id']}"

        with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.hset(jogo_key, mapping=jogo)
            pipeline.sadd("jogos:ids", jogo["id"])
            pipeline.execute()

        return jogo


jogo_repository = JogoRepository()
