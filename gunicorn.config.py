import logging
from multiprocessing import cpu_count

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s %(levelname)-8s %(message)s',
	filename='ride-share.log'
)
logger = logging.getLogger()

bind = '127.0.0.1:80'
backlog = 256

workers = cpu_count() + 1
threads = cpu_count() + 1
worker_class = 'gevent'
worker_connections = 100

timeout = 30
keepalive = 2

accesslog = 'rideshare-access.log'
errorlog = 'rideshare-error.log'
loglevel = 'info'
spew = False
