import logging

from database import counters_collection

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="ride-share.log",
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


def pre_request(worker, req):
	if req.path != "/":
		logger.info(f"G {req.path} {req.method} {req.headers}")
	try:
		if "/api/v1/users" in req.path:
			a = counters_collection.find_one_and_update(
				{"_id": "requests"}, {"$inc": {"req_count": 1}}, upsert=True
			)
			logger.info(f"Counter updated - {[a['req_count'] + 1 if a else 1]}")
	except Exception as e:
		logger.error(f"DBWrite error while updating counter. Error: {e}")
