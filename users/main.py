"""
	RideShare (Cloud Computing Project)
	main.py: python file containing the user API logic
"""

import logging
from json import dumps
from typing import List

import redis
import requests
from flask import Flask, request
from flask_restful import Api, Resource, reqparse

from config import dbaas_ip, flask_port, redis_host, redis_key

# Paths for API endpoints
url_prefix = "/api/v1"
base_url_db = f"http://{dbaas_ip}{url_prefix}/db"
url_db_write = f"{base_url_db}/write"
url_db_read = f"{base_url_db}/read"

# Standard headers to be sent with every DB request
headers = {"Content-Type": "application/json"}

# SHA1 charset
hex_set = set("0123456789abcdef")

# Logger
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="rideshare.log",
)
logger = logging.getLogger()

app = Flask(__name__)
api = Api(app)

# fetching the JSON body arguments for a request
parser = reqparse.RequestParser()
parser.add_argument("username", type=str)
parser.add_argument("password", type=str)

# Connecting to redis
r = redis.Redis(host=redis_host)


def is_valid_sha(password: str) -> bool:
	"""
	Return is `password` is a valid SHA1 string /[a-f0-9]{40}/
	"""
	return len(password) == 40 and not set(password.lower()) - hex_set


def insert_user(user: dict) -> bool:
	"""
	Helper function to send request to DB to insert `user`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "users", "action": 0, "document": user}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB insert_user {user} -> {res}")
	return res


def find_users(filte: dict) -> List[dict]:
	"""
	Helper function to send request to DB to find user(s) on query `filte`
	Returns list of ride documents from DB
	"""
	payload = {"collection": "users", "filte": filte}
	res = requests.post(url_db_read, data=dumps(payload), headers=headers).json()
	logger.info(f"DB find_users {filte} -> {res}")
	return res


def update_rides(filte: dict, update: dict) -> bool:
	"""
	Helper function to send request to DB to update ride(s) on query `filte`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "rides", "action": 1, "filte": filte, "update": update}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB update_rides {filte} {update} -> {res}")
	return res


def delete_users(filte: dict) -> bool:
	"""
	Helper function to send request to DB to delete user(s) on query `filte`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "users", "action": 2, "filte": filte}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB delete_users {filte} -> {res}")
	return res


def delete_rides(filte: dict) -> bool:
	"""
	Helper function to send request to DB to find ride(s) on query `filte`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "rides", "action": 2, "filte": filte}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB delete_rides {filte} -> {res}")
	return res


class Home(Resource):
	def get(self):
		return {'message': 'Ok. Users Running'}, 200


class RequestCount(Resource):
	def get(self):
		"""
		summary: endpoint to obtain the request count on any of the ride APIs
		path: /api/v1/_count
		method: get
		responses:
			200:
				description: OK
				content: application/json
				type: array
				items:
					type: integer
		"""
		return [int(r.get(redis_key) or 0)], 200

	def delete(self):
		"""
		summary: endpoint to reset the request count on any of the ride APIs
		path: /api/v1/_count
		method: delete
		responses:
			200: OK
		"""
		r.delete(redis_key)
		return {}, 200


class Users(Resource):
	def put(self):
		"""
		summary: endpoint for inserting a user
		path: /api/v1/users
		method: put
		requestBody:
			content: application/json
			type: object
			requestBody:
        content: application/json
				type: object
				properties:
					username:
						type: string
					password:
						type: string
						description: SHA1 encrypted password
			required:
				- username
				- password
		responses:
			201: User Created
			400: Bad Request. Username exists or invalid password
		"""
		logger.debug(request.get_json())
		# Fetch request body into a dict-like object
		args = parser.parse_args()
		username, password = args["username"], args["password"]

		# Bad Request if password is invalid
		if not is_valid_sha(password):
			return {}, 400

		# Bad request if username already exists
		query = {"username": username}
		if find_users(query):
			return {}, 400

		insert_user({"username": username, "password": password})

		return {}, 201

	def get(self):
		"""
		summary: endpoint for fetching all username
		path: /api/v1/users
		method: get
		responses:
			200:
				description: OK
				content: application/json
				type: array
				items:
					type: object
					properties:
						username:
							type: string
			204:
				description: No Users
		"""
		r = [user["username"] for user in find_users({})]

		return r, 200 if r else 204


class User(Resource):
	def delete(self, username):
		"""
		summary: endpoint for deleting user with `username`
		path: /api/v1/users
		method: delete
		parameters:
			type: string
			name: username
			in: path
			required: true
		responses:
			200: OK
			400: Bad Request. User does not exist
		"""
		# Bad Request if user does not exist
		query = {"username": username}
		if not find_users(query):
			return {}, 400

		delete_users(query)

		# Delete rides created by user
		query = {"created_by": username}
		delete_rides(query)

		# Remove users from rides they have joined
		query = {"users": username}
		update_rides(query, {"$pull": query})

		return {}, 200


api.add_resource(Home, "/")
api.add_resource(RequestCount, f"{url_prefix}/_count")
api.add_resource(Users, f"{url_prefix}/users")
api.add_resource(User, f"{url_prefix}/users/<string:username>")


if __name__ == "__main__":
	app.run(port=flask_port, host="0.0.0.0", debug=True)
