import logging
from json import dumps
from typing import List

import requests
from flask import Flask, request
from flask_restful import Api, Resource, reqparse

from config import flask_ips as ips
from config import flask_ports as ports
from database import counters_collection, users_collection

url_prefix = "/api/v1"
port_users = ports.docker
port_rides = ports.extern
ip_users = ips.docker
ip_rides = ips.extern
base_url_users = f"http://{ip_users}:{port_users}{url_prefix}"
base_url_rides = f"http://{ip_rides}:{port_rides}{url_prefix}"

headers = {"Content-Type": "application/json"}

hex_set = set("0123456789abcdef")

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
parser.add_argument("username", type=str)
parser.add_argument("password", type=str)


def is_valid_sha(password: str):
	return len(password) == 40 and not set(password.lower()) - hex_set


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

			if action == 0:
				users_collection.insert_one(document)
			elif action == 2:
				users_collection.delete_many(filte)

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

			r = list(users_collection.find(filte, {"_id": 0}))

		except Exception as e:
			logger.error(f"DBRead error. args: {args}. Error: {e}")
			return [], 400

		return r, 200


class DBClear(Resource):
	def post(self):
		try:
			users_collection.delete_many({})

		except Exception as e:
			logger.error(f"DBClear error. Error: {e}")
			return {}, 400

		return {}, 200


def insert_user(document: dict):
	url = f"{base_url_users}/db/write"
	payload = {"action": 0, "document": document}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def find_users(filte: dict) -> List[dict]:
	url = f"{base_url_users}/db/read"
	payload = {"filter": filte}
	return requests.post(url, data=dumps(payload), headers=headers).json()


def update_rides(filte: dict, update: dict):
	url = f"{base_url_rides}/db/write"
	payload = {"action": 1, "filter": filte, "update": update}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def delete_users(filte: dict):
	url = f"{base_url_users}/db/write"
	payload = {"action": 2, "filter": filte}
	return requests.post(url, data=dumps(payload), headers=headers).ok


def delete_rides(filte: dict):
	url = f"{base_url_rides}/db/write"
	payload = {"action": 2, "filter": filte}
	return requests.post(url, data=dumps(payload), headers=headers).ok


class Users(Resource):
	def put(self):
		logger.info(request.get_json())
		args = parser.parse_args()
		username, password = args["username"], args["password"]

		if not is_valid_sha(password):
			return {}, 400

		query = {"username": username}
		if find_users(query):
			return {}, 400

		insert_user({"username": username, "password": password})

		return {}, 201

	def get(self):
		r = [user["username"] for user in find_users({})]

		return r, 200 if r else 204


class User(Resource):
	def delete(self, username):

		query = {"username": username}
		if not find_users(query):
			return {}, 400

		delete_users(query)

		query = {"created_by": username}
		delete_rides(query)

		query = {"users": username}
		update_rides(query, {"$pull": query})

		return {}, 200


api.add_resource(Users, f"{url_prefix}/users")
api.add_resource(User, f"{url_prefix}/users/<string:username>")
api.add_resource(DBWrite, f"{url_prefix}/db/write")
api.add_resource(DBRead, f"{url_prefix}/db/read")
api.add_resource(DBClear, f"{url_prefix}/db/clear")
api.add_resource(RequestsDB, f"{url_prefix}/_count")


if __name__ == "__main__":
	app.run(port=port_users, host="0.0.0.0", debug=True)
