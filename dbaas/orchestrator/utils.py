"""
	RideShare (Cloud Computing Project)
	utils.py: helper functions for orchestrator/main.py
"""

import logging
import threading
from contextlib import contextmanager
from math import ceil
from time import sleep
from typing import List
from uuid import uuid4

import docker
import pika
import redis

from config import redis_host, redis_key, rmq_host

# ## Logger
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="orchestrator.log",
)
logger = logging.getLogger()

# ## Redis
# Connect to Redis
r = redis.Redis(host=redis_host)


# Redis helper functions
def get_redis_count(redis_key: str = redis_key) -> int:
	# Returns value of `redis_key` if it exists, else None
	return int(r.get(redis_key) or 0)


def incr_redis_count(redis_key: str = redis_key) -> int:
	# Increments `redis_key` by 1 if it exists, else sets it to 1
	return r.incr(redis_key)


def reset_redis_count(redis_key: str = redis_key) -> int:
	# Deletes `redis_key` and returns 1 if it exists, else 0
	return r.delete(redis_key)


# ## UUID
def new_uuid() -> str:
	"""
	Returns a unique random UUID
	"""
	return str(uuid4())


# ## RMQ
@contextmanager
def rabbit_channel(rmq_host=rmq_host):
	"""
	Connects to RMQ, generates a channel and closes the connection when processing is done
	"""
	try:
		connection = pika.BlockingConnection(
			pika.ConnectionParameters(host=rmq_host, heartbeat=0)
		)
		yield connection.channel()
	except Exception as e:
		logger.error(f"Error connecting to RMQ. {e}")
	finally:
		connection.close()


q_names = ["writeQ", "readQ", "respQ", "syncQ"]

# Declare required queues
with rabbit_channel() as rmq_channel:
	for q_name in q_names:
		try:
			rmq_channel.queue_declare(queue=q_name, durable=True)
		except Exception as e:
			logger.error(f"Error while declaring queue {q_name}. {e}")


def push_to_Q(queue: str, query: str):
	"""
	Helper function to publish a `query` in a queue
	Uses the default exchange and persistent delivery mode
	"""
	with rabbit_channel() as rmq_channel:
		rmq_channel.basic_publish(
			exchange="",
			routing_key=queue,
			body=query,
			properties=pika.BasicProperties(delivery_mode=2),
		)


class ReadRpcClient:
	"""
	Sends `query` to readQ via call() and returns response sent by worker to respQ
	"""
	def __init__(self, rmq_host=rmq_host):
		"""
		Setup RMQ connection and response queue consumption
		"""
		self.connection = pika.BlockingConnection(
			pika.ConnectionParameters(host=rmq_host, heartbeat=0)
		)
		self.channel = self.connection.channel()
		self.callback_queue = "respQ"
		self.channel.basic_consume(
			queue=self.callback_queue,
			on_message_callback=self.on_response,
			auto_ack=True,
		)

	def on_response(self, ch, method, props, body):
		"""
		Triggered when a response is received in respQ.
		Checks if correlation_id of response is same as the one sent with the request
		"""
		if self.corr_id == props.correlation_id:
			self.response = body.decode("utf-8")

	def call(self, query) -> str:
		"""
		Sends the actual `query` to readQ with a unique correlation_id using default exchange
		Informs the readQ listener to send back response to respQ
		"""
		self.response = None
		self.corr_id = new_uuid()
		self.channel.basic_publish(
			body=query,
			exchange="",
			routing_key="readQ",
			properties=pika.BasicProperties(
				correlation_id=self.corr_id, reply_to=self.callback_queue
			),
		)

		# Close the connection, once the response is received
		while self.response is None:
			self.connection.process_data_events()
		else:
			self.connection.close()

		return self.response


# ## Docker
docker_client = docker.from_env()


# Docker SDK helper function
def list_containers() -> List[docker.models.containers.Container]:
	"""
	Returns a list of Container objects of all running containers
	"""
	return docker_client.containers.list()


def list_slaves() -> List[docker.models.containers.Container]:
	"""
	Returns a list of Container objects of all running slave containers
	"""
	return [c for c in list_containers() if "worker-slave" in c.name]


def list_workers() -> List[docker.models.containers.Container]:
	"""
	Returns a list of Container objects of all running worker containers (master/slave)
	"""
	return [c for c in list_containers() if "worker" in c.name]


def container_pid(c: docker.models.containers.Container) -> int:
	"""
	returns PID of `c` according in the host namespace
	"""
	return int(c.top()["Processes"][0][1])


def worker_pids() -> List[int]:
	"""
	Returns a list of PIDs of all running worker containers (master/slave)
	"""
	return sorted(map(container_pid, list_workers()))


def spawn_slave() -> int:
	"""
	Spawn a new slave container on the dbaas_default network and returns its PID
	"""
	n = r.incr("slave-count") + 1
	logger.info(f"Spawning Slave {n}")
	c = docker_client.containers.run(
		image="worker-slave",
		command=f"python3 main.py {n}",
		name=f"worker-slave-{n}",
		hostname=f"worker-slave-{n}",
		network="dbaas_default",
		restart_policy={"Name": "on-failure"},
		detach=True,
	)
	sleep(0.5)
	return container_pid(c)


def kill_slave(scaling: bool = False) -> int:
	"""
	Kills the slave with max PID and returns the PID
	"""
	# Find slave
	c = max(list_slaves(), key=container_pid)
	# Find PID
	p = container_pid(c)
	# Kill slave
	c.kill()
	sleep(0.5)
	if not scaling: spawn_slave()
	return p


def scale_down(n: int) -> List[int]:
	"""
	Kills `n` slave containers and returns their PIDs
	"""
	logger.info(f"Scaling Down by {n} nodes")
	return [kill_slave(scaling=True) for i in range(n)]


def scale_up(n: int) -> List[int]:
	"""
	Spawns `n` new slave containers and returns their PIDs
	"""
	logger.info(f"Scaling Up by {n} nodes")
	return [spawn_slave() for i in range(n)]


def scale_daemon():
	"""
	Spawns or kills slave containers based on number of requests received in the last 120 seconds
	"""
	# call this function after another 120 seconds
	scale_after(120)
	logger.info("Scaler Daemon")
	# Check number of requests received
	req_count = get_redis_count()
	# Reset request count to 0
	reset_redis_count()
	# Check number of running slave containers
	slave_count = len(list_slaves())
	# Calculate delta
	additional_slaves_req = max(ceil(req_count / 20), 1) - slave_count
	# Need more
	if additional_slaves_req > 0: scale_up(additional_slaves_req)
	# Have more
	elif additional_slaves_req < 0: scale_down(-additional_slaves_req)


def scale_after(interval: int):
	"""
	Calls the scaler after `interval` seconds on a separate thread
	"""
	threading.Timer(interval, scale_daemon).start()
