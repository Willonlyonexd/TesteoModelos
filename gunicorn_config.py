bind = "0.0.0.0:$PORT"
workers = 2
threads = 2
timeout = 500
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
worker_class = "sync"  # Evitamos gevent para inicio más rápido