# Tuning de postgresql.conf (F:\PGDATA\postgresql.conf) — VM 32 GB RAM
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 128MB
maintenance_work_mem = 2GB
max_wal_size = 8GB
checkpoint_completion_target = 0.9
wal_compression = on
random_page_cost = 1.1
autovacuum = on
# Reiniciar el servicio PostgreSQL tras cambiar este archivo.
