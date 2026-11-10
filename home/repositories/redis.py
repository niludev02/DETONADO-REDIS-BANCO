from redis import Redis


RedisClient = Redis


def get_redis_client():
    return Redis.from_url("redis://localhost:6379/0")
