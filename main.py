import logging
from datetime import datetime
from json import dumps
from typing import List

import requests
from flask import Flask, request
from flask_restful import Api, Resource, reqparse

from database import db
from locations import locations
from password import isValidSHA

# from functools import partial
# from bson import json_util
# from termcolor import colored

port = 5000
url_prefix = "/api/v1"
ip_addr = "localhost"
base_url = f"http://{ip_addr}:{port}{url_prefix}"

# dumps = partial(dumps, default=str)
# dumps = partial(dumps, default=json_util.default)

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="rideshare.log",
)
logger = logging.getLogger()

app = Flask(__name__)
api = Api(app)

parser = reqparse.RequestParser()
parser.add_argument("action", type=int)
parser.add_argument("collection", type=str)
parser.add_argument("document", type=dict)
parser.add_argument("filter", type=dict)
parser.add_argument("update", type=dict)
parser.add_argument("username", type=str)
parser.add_argument("password", type=str)
parser.add_argument("created_by", type=str)
parser.add_argument("timestamp", type=str)
parser.add_argument("source", type=int)
parser.add_argument("destination", type=int)


class DBWrite(Resource):
	def post(self):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		try:
			args = parser.parse_args()
			action = args["action"]
			collection = args["collection"]
			document = args["document"]
			filte = args["filter"]
			update = args["update"]

			if action == 0:
				db[collection].insert_one(document)
			elif action == 1:
				db[collection].update_many(filte, update)
			elif action == 2:
				db[collection].delete_many(filte)
			elif action == 3:
				return (
					{
						"id": db["counters"].find_one_and_update(
							{"_id": "rideid"},
							{"$inc": {"sequence_value": 1}},
							upsert=True,
						)["sequence_value"]
					},
					201,
				)

			else:
				return {}, 400

		except Exception as e:
			logger.error(f"DBWrite error. args: {args}. Error: {e}")
			return {}, 400

		return {}, 201


class DBRead(Resource):
	def post(self):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		try:
			args = parser.parse_args()
			collection = args["collection"]
			filte = args["filter"]

			r = list(db[collection].find(filte, {"_id": 0}))

		except Exception as e:
			logger.error(f"DBRead error. args: {args}. Error: {e}")
			return [], 400

		return r, 200


def insert(collection: str, document: dict):
	url = f"{base_url}/write"
	payload = {"action": 0, "collection": collection, "document": document}
	headers = {"Content-Type": "application/json"}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def find(collection: str, filte: dict) -> List[dict]:
	url = f"{base_url}/read"
	payload = {"collection": collection, "filter": filte}
	headers = {"Content-Type": "application/json"}
	return requests.post(url, data=dumps(payload), headers=headers).json()


def update(collection: str, filte: dict, update: dict):
	url = f"{base_url}/write"
	payload = {"action": 1, "collection": collection, "filter": filte, "update": update}
	headers = {"Content-Type": "application/json"}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def delete(collection: str, filte: dict):
	url = f"{base_url}/write"
	payload = {"action": 2, "collection": collection, "filter": filte}
	headers = {"Content-Type": "application/json"}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def next_id():
	url = f"{base_url}/write"
	payload = {"action": 3}
	headers = {"Content-Type": "application/json"}
	return requests.post(url, data=dumps(payload), headers=headers).json()["id"]


class Users(Resource):
	def put(self):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		args = parser.parse_args()
		username, password = args["username"], args["password"]

		if not isValidSHA(password):
			return {}, 400

		query = {"username": username}
		if find("users", query):
			return {}, 400

		insert("users", {"username": username, "password": password})

		return {}, 201


class User(Resource):
	def delete(self, username):
		logger.info(f"{request.method} {request.base_url} {request.data}")

		query = {"username": username}
		if not find("users", query):
			return {}, 400

		delete("users", query)

		query = {"created_by": username}
		delete("rides", query)

		query = {"users": username}
		update("rides", query, {"$pull": query})

		return {}, 200


class Rides(Resource):
	def post(self):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		args = parser.parse_args()
		created_by = args["created_by"]
		timestamp = args["timestamp"]
		source = args["source"]
		destination = args["destination"]

		query = {"username": created_by}
		if not find("users", query) \
			or source not in locations \
			or destination not in locations \
			or source == destination:
			return {}, 400

		id_ = next_id()

		try:
			timestamp = int(
				datetime.strptime(timestamp, "%d-%m-%Y:%S-%M-%H").timestamp()
			)
		except Exception:
			return {}, 400

		if timestamp < int(datetime.now().timestamp()):
			return {}, 400

		insert(
			"rides",
			{
				"rideId": id_,
				"created_by": created_by,
				"timestamp": timestamp,
				"users": [],
				"source": source,
				"destination": destination,
			},
		)

		return {}, 201

	def get(self):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		args = request.args
		source = int(args["source"])
		destination = int(args["destination"])

		if source not in locations or destination not in locations:
			return {}, 400

		query = {
			"source": source,
			"destination": destination,
			"timestamp": {"$gt": int(datetime.now().timestamp())},
		}
		r = find("rides", query)

		if not r:
			return [], 204

		for r_ in r:
			r_["timestamp"] = datetime.fromtimestamp(r_["timestamp"]).strftime(
				"%d-%m-%Y:%S-%M-%H"
			)

		return r, 200


class Ride(Resource):
	def get(self, rideid):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		query = {"rideId": rideid}
		r = find("rides", query)

		if not r:
			return {}, 400

		r[0]["timestamp"] = datetime.fromtimestamp(r[0]["timestamp"]).strftime(
			"%d-%m-%Y:%S-%M-%H"
		)

		return r[0], 200

	def post(self, rideid):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		args = parser.parse_args()
		username = args["username"]

		r = find("rides", {"rideId": rideid})

		if not find("users", {"username": username}) \
			or not r \
			or r[0]["created_by"] == username \
			or username in r[0]["users"]:
			return {}, 400

		update("rides", {"rideId": rideid}, {"$push": {"users": username}})

		return {}, 200

	def delete(self, rideid):
		logger.info(f"{request.method} {request.base_url} {request.data}")
		query = {"rideId": rideid}

		if not find("rides", query):
			return {}, 400

		delete("rides", query)

		return {}, 200


api.add_resource(Users, f"{url_prefix}/users")
api.add_resource(User, f"{url_prefix}/users/<string:username>")
api.add_resource(Rides, f"{url_prefix}/rides")
api.add_resource(Ride, f"{url_prefix}/rides/<int:rideid>")
api.add_resource(DBWrite, f"{url_prefix}/write")
api.add_resource(DBRead, f"{url_prefix}/read")


if __name__ == "__main__":
	app.run(port=port, threaded=True, debug=True)
