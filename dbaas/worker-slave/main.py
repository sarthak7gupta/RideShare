"""
	RideShare (Cloud Computing Project)
	main.py: python file containing the DB Slave-worker logic
"""

from json import dumps, loads
from sys import argv
from time import sleep
from typing import Any

import pika

from utils import (logger, mongo_collection, push_to_Q, rabbit_channel,
                   start_mongo)


def read_db(collection: str, filte: dict = {}) -> Any:
	"""
	Returns list of documents from `collection` on query `filte`
	"""
	logger.info(f"Read DB {collection} {filte}")
	with mongo_collection(collection) as collection:
		return list(collection.find(filte, {"_id": 0}))


def read_db_callback(ch, method, props, body):
	"""
	Returns the data from DB to the respQ with the correlation_id received with query
	"""
	args = loads(body.decode("utf-8"))
	logger.info(f"Read {body}")
	# Reads from the DB
	response = read_db(args["collection"], args["filte"])

	# Publish the data back to the callback queue and acknowledge message
	ch.basic_publish(
		exchange="",
		routing_key=props.reply_to,
		properties=pika.BasicProperties(correlation_id=props.correlation_id),
		body=dumps(response),
	)
	ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
	# Starts the Mongo daemon on the worker host
	start_mongo()

	# Notifying master to add you as a worker in the Mongo ReplSet
	push_to_Q("syncQ", f"worker-slave-{argv[1]}")

	sleep(3)

	# Listen to read requests on readQ
	with rabbit_channel() as channel:
		channel.basic_consume(queue="readQ", on_message_callback=read_db_callback)
		logger.info("Listening for requests...")
		channel.start_consuming()
