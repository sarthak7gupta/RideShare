from utils import logger

bind = "0.0.0.0:5000"
backlog = 256

workers = 1
threads = 1
worker_class = "gevent"
worker_connections = 100

timeout = 30
keepalive = 2

accesslog = "orchestrator-access.log"
errorlog = "orchestrator-error.log"
loglevel = "info"
spew = False


def pre_request(worker, req):
	if req.path != "/":
		logger.info(f"G {req.path} {req.method} {req.headers}")
