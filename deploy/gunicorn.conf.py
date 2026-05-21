# deploy/gunicorn.conf.py
# Production Gunicorn config for uvicorn workers

import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Workers
# Rule of thumb: (2 * CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 300           # 5 min — transcription can take a while
keepalive = 5
max_requests = 1000     # restart workers after N requests (prevents memory leaks)
max_requests_jitter = 100

# Logging
accesslog = "-"         # stdout
errorlog = "-"          # stdout
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "stt_platform"

# Graceful shutdown
graceful_timeout = 30   # wait up to 30s for workers to finish