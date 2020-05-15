import logging
from datetime import datetime
from json import dumps
from typing import List

import requests
from flask import Flask, request
from flask_restful import Api, Resource, reqparse

from config import flask_ips as ips
from config import flask_ports as ports
from database import counters_collection, rides_collection
from locations import locations

url_prefix = "/api/v1"
port_rides = ports.docker
port_users = ports.extern
ip_rides = ips.docker
ip_users = ips.extern
base_url_rides = f"http://{ip_rides}:{port_rides}{url_prefix}"
base_url_users = f"http://{ip_users}:{port_users}{url_prefix}"

headers = {"Content-Type": "application/json"}

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
parser.add_argument("document", type=dict)
parser.add_argument("filter", type=dict)
parser.add_argument("update", type=dict)
parser.add_argument("username", type=str)
parser.add_argument("created_by", type=str)
parser.add_argument("timestamp", type=str)
parser.add_argument("source", type=int)
parser.add_argument("destination", type=int)


class RequestsDB(Resource):
	def get(self):
		try:
			a = list(counters_collection.find({"_id": "requests"}))
			return [a[0]["req_count"] if a else 0], 200

		except Exception as e:
			logger.error(f"DBWrite error. Error: {e}")
			return [], 400

	def delete(self):
		try:
			counters_collection.find_one_and_update(
				{"_id": "requests"}, {"$set": {"req_count": 0}}, upsert=True
			)
			return {}, 200

		except Exception as e:
			logger.error(f"DBWrite error. Error: {e}")
			return {}, 400


class DBWrite(Resource):
	def post(self):
		try:
			args = parser.parse_args()
			action = args["action"]
			document = args["document"]
			filte = args["filter"]
			update = args["update"]

			if action == 0:
				rides_collection.insert_one(document)
			elif action == 1:
				rides_collection.update_many(filte, update)
			elif action == 2:
				rides_collection.delete_many(filte)
			elif action == 3:
				a = counters_collection.find_one_and_update(
					{"_id": "rideid"}, {"$inc": {"sequence_value": 1}}, upsert=True
				)
				return {"id": a["sequence_value"] + 1 if a else 1}, 201

			else:
				return {}, 400

		except Exception as e:
			logger.error(f"DBWrite error. args: {args}. Error: {e}")
			return {}, 400

		return {}, 201


class DBRead(Resource):
	def post(self):
		try:
			args = parser.parse_args()
			filte = args["filter"]

			r = list(rides_collection.find(filte, {"_id": 0}))

		except Exception as e:
			logger.error(f"DBRead error. args: {args}. Error: {e}")
			return [], 400

		return r, 200


class DBClear(Resource):
	def post(self):
		try:
			rides_collection.delete_many({})

		except Exception as e:
			logger.error(f"DBClear error. Error: {e}")
			return {}, 400

		return {}, 200


def insert_ride(document: dict):
	url = f"{base_url_rides}/db/write"
	payload = {"action": 0, "document": document}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def find_rides(filte: dict) -> List[dict]:
	url = f"{base_url_rides}/db/read"
	payload = {"filter": filte}
	return requests.post(url, data=dumps(payload), headers=headers).json()


def update_rides(filte: dict, update: dict):
	url = f"{base_url_rides}/db/write"
	payload = {"action": 1, "filter": filte, "update": update}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def delete_rides(filte: dict):
	url = f"{base_url_rides}/db/write"
	payload = {"action": 2, "filter": filte}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def find_users() -> List[str]:
	url = f"{base_url_users}/users"
	headers.update({"Origin": "3.232.243.208"})
	a = requests.get(url, headers=headers)
	return a.json() if a.status_code != 204 else []


def next_id():
	url = f"{base_url_rides}/db/write"
	payload = {"action": 3}
	return requests.post(url, data=dumps(payload), headers=headers).json()["id"]


class Rides(Resource):
	def post(self):
		logger.info(request.get_json())
		args = parser.parse_args()
		created_by = args["created_by"]
		timestamp = args["timestamp"]
		source = args["source"]
		destination = args["destination"]

		if created_by not in find_users() \
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

		insert_ride(
			{
				"rideId": id_,
				"created_by": created_by,
				"timestamp": timestamp,
				"users": [],
				"source": source,
				"destination": destination,
			}
		)

		return {}, 201

	def get(self):
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
		r = find_rides(query)

		if not r:
			return [], 204

		for r_ in r:
			r_["timestamp"] = datetime.fromtimestamp(r_["timestamp"]).strftime(
				"%d-%m-%Y:%S-%M-%H"
			)

		return r, 200


class RideCount(Resource):
	def get(self):
		return [len(find_rides({}))], 200


class Ride(Resource):
	def get(self, rideid):
		query = {"rideId": rideid}
		r = find_rides(query)

		if not r:
			return {}, 400

		timestamp = r[0]["timestamp"]

		if timestamp < int(datetime.now().timestamp()):
			return {}, 400

		r[0]["timestamp"] = datetime.fromtimestamp(timestamp).strftime(
			"%d-%m-%Y:%S-%M-%H"
		)

		return r[0], 200

	def post(self, rideid):
		logger.info(request.get_json())
		args = parser.parse_args()
		username = args["username"]

		query = {"rideId": rideid}
		r = find_rides(query)

		if username not in find_users() \
			or not r \
			or r[0]["created_by"] == username \
			or username in r[0]["users"]:
			return {}, 400

		update_rides({"rideId": rideid}, {"$push": {"users": username}})

		return {}, 200

	def delete(self, rideid):
		query = {"rideId": rideid}

		if not find_rides(query):
			return {}, 400

		delete_rides(query)

		return {}, 200


api.add_resource(Rides, f"{url_prefix}/rides")
api.add_resource(Ride, f"{url_prefix}/rides/<int:rideid>")
api.add_resource(RideCount, f"{url_prefix}/rides/count")
api.add_resource(DBWrite, f"{url_prefix}/db/write")
api.add_resource(DBRead, f"{url_prefix}/db/read")
api.add_resource(DBClear, f"{url_prefix}/db/clear")
api.add_resource(RequestsDB, f"{url_prefix}/_count")


if __name__ == "__main__":
	app.run(port=port_rides, host="0.0.0.0", debug=True)
