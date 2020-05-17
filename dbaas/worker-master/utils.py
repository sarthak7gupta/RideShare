"""
	RideShare (Cloud Computing Project)
	utils.py: helper functions for worker-master/main.py
"""

import logging
from contextlib import contextmanager
from os import system
from time import sleep

import pika
from pymongo import MongoClient

from config import mongodb_host, rmq_host

# ## Logger
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="worker-master.log",
)
logger = logging.getLogger()


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


q_names = ["writeQ", "syncQ"]

# Declare required queues
with rabbit_channel(rmq_host) as rmq_channel:
	for q_name in q_names:
		try:
			rmq_channel.queue_declare(queue=q_name, durable=True)
		except Exception as e:
			logger.error(f"Error while declaring queue {q_name}. {e}")


# ## Mongo
def start_mongo(mongo_host=mongodb_host):
	"""
	Starts the mongo daemon with the ReplSet option in the background
	"""
	system(f"mongod --replSet rs0 --bind_ip {mongo_host} --port 27017 &")
	sleep(30)


@contextmanager
def mongo_collection(collection, mongo_host=mongodb_host):
	"""
	Connects to mongo,
	returns the collection object of `collection`,
	and closes the connection after processing is done
	"""
	try:
		client = MongoClient(mongo_host, 27017, readPreference="secondaryPreferred")
		yield client["cc"][collection]
	except Exception as e:
		logger.error(f"Error connecting to MongoDB. {e}")
	finally:
		client.close()


@contextmanager
def mongo_connection(mongo_host=mongodb_host):
	"""
	Connects to mongo, returns the connection object and closes the connection after processing is done
	"""
	try:
		client = MongoClient(mongo_host, 27017, readPreference="secondaryPreferred")
		yield client
	except Exception as e:
		logger.error(f"Error connecting to MongoDB. {e}")
	finally:
		client.close()
