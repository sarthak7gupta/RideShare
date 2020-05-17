import logging

import redis

from config import redis_host, redis_key

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="rideshare.log",
)
logger = logging.getLogger()

bind = "0.0.0.0:5000"
backlog = 256

workers = 1
threads = 1
worker_class = "gevent"
worker_connections = 100

timeout = 30
keepalive = 2

accesslog = "rideshare-access.log"
errorlog = "rideshare-error.log"
loglevel = "info"
spew = False

r = redis.Redis(host=redis_host)


def pre_request(worker, req):
	"""
	Server hook used for incrementing request count before Flask handles it.
	"""
	if req.path != "/":
		logger.info(f"G {req.path} {req.method} {req.headers}")
	if "/api/v1/rides" in req.path:
		a = r.incr(redis_key)
		logger.info(f"Counter updated - {a}")
