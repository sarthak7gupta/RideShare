"""
	RideShare (Cloud Computing Project)
	main.py: python file containing the DB Master-worker logic
"""

from json import loads
from threading import Thread

from utils import (logger, mongo_collection, mongo_connection, rabbit_channel,
				   start_mongo)


def write_db(
	collection: dict = {},
	action: dict = {},
	document: dict = {},
	filte: dict = {},
	update: dict = {},
	**kwargs,
):
	"""
	Performs the actual write operations onto the database
	"""
	logger.info(f"Write to DB {collection} {action} {document} {filte} {update}")
	with mongo_collection(collection) as collection:
		if action == 0:
			collection.insert_one(document)
		elif action == 1:
			collection.update_many(filte, update)
		elif action == 2:
			collection.delete_many(filte)


def write_db_callback(ch, method, props, body):
	"""
	Acknowledge message after writing to DB
	"""
	args = loads(body.decode("utf-8"))
	logger.info(f"Write {body}")

	write_db(**args)

	ch.basic_ack(delivery_tag=method.delivery_tag)


def mongo_sync_callback(ch, method, props, body):
	"""
	Add new slave worker to Mongo ReplSet
	"""
	body = body.decode("utf-8")
	logger.info(f"syncQ {body}")
	n = int(body.rsplit("-", maxsplit=1)[-1])
	with mongo_connection() as conn:
		conf = conn.admin.command({"replSetGetConfig": 1})
		conf["config"]["members"].append(
			{"_id": n, "host": f"{body}:27017", "hidden": True, "priority": 0}
		)
		conf["config"]["version"] += 1
		res = conn.admin.command({"replSetReconfig": conf["config"]})
		logger.info(res)
	ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_sync():
	"""
	Listens for new slave workers
	"""
	logger.info("Consuming Sync")
	with rabbit_channel() as channel:
		channel.basic_consume(queue="syncQ", on_message_callback=mongo_sync_callback)
		channel.start_consuming()


if __name__ == "__main__":
	# Starts the Mongo daemon on the worker host
	start_mongo()

	# Establish yourself as master of Mongo ReplSet
	with mongo_connection() as conn:
		config = {"_id": "rs0", "members": [{"_id": 0, "host": "worker-master:27017"}]}
		conn.admin.command("replSetInitiate", config)

	# Listen to new workers on a separate thread
	t = Thread(target=consume_sync).start()

	# Listen to write requests on writeQ
	with rabbit_channel() as channel:
		channel.basic_consume(queue="writeQ", on_message_callback=write_db_callback)
		logger.info("Listening for requests...")
		channel.start_consuming()
