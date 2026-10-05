import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "sync"
timeout = 120
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
worker_tmp_dir = "/tmp"
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "172.30.80.1,127.0.0.1,::1")
# Never log URI/query, referer, cookies or authorization headers (QR/reset tokens).
accesslog = "-"
access_log_format = "%(t)s method=%(m)s status=%(s)s bytes=%(B)s duration=%(L)s"
errorlog = "-"
capture_output = True
umask = 0o077
