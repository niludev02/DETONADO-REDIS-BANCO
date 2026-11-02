import redis

# Configuração da conexão com Redis
redis_conn = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

# Testa a conexão com o Redis
try:
    redis_conn.ping()
    print("Conexão com Redis estabelecida!")
except redis.ConnectionError:
    print("Erro ao conectar com Redis.")
