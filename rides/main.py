"""
	RideShare (Cloud Computing Project)
	main.py: python file containing the rides API logic
"""

import logging
from datetime import datetime
from json import dumps
from typing import List

import redis
import requests
from flask import Flask, request
from flask_restful import Api, Resource, reqparse

from config import dbaas_ip, elb_ip, flask_port, redis_host, redis_key, rides_ip
from locations import locations

# Paths for API endpoints
url_prefix = "/api/v1"
url_users = f"http://{elb_ip}{url_prefix}/users"
base_url_db = f"http://{dbaas_ip}{url_prefix}/db"
url_db_write = f"{base_url_db}/write"
url_db_read = f"{base_url_db}/read"

# Standard headers to be sent with every DB request
headers = {"Content-Type": "application/json"}

# Logger
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)-8s %(message)s",
	filename="rideshare.log",
)
logger = logging.getLogger()

# Flask RESTful Setup
app = Flask(__name__)
api = Api(app)

# Defining arguments used by REST endpoints in JSON body
parser = reqparse.RequestParser()
parser.add_argument("username", type=str)
parser.add_argument("created_by", type=str)
parser.add_argument("timestamp", type=str)
parser.add_argument("source", type=int)
parser.add_argument("destination", type=int)

# Connect to Redis
r = redis.Redis(host=redis_host)


def insert_ride(ride: dict) -> bool:
	"""
	Helper function to send request to DB to insert `ride`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "rides", "action": 0, "document": ride}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB insert_ride {ride}-> {res}")
	return res


def find_rides(filte: dict) -> List[dict]:
	"""
	Helper function to send request to DB to find ride(s) on query `filte`
	Returns list of ride documents from DB
	"""
	payload = {"collection": "rides", "filte": filte}
	res = requests.post(url_db_read, data=dumps(payload), headers=headers).json()
	logger.info(f"DB find_rides {filte}-> {res}")
	return res


def update_rides(filte: dict, update: dict):
	"""
	Helper function to send request to DB to set `update` to ride(s) on query `filte`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "rides", "action": 1, "filte": filte, "update": update}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB update_rides {filte}-> {res}")
	return res


def delete_rides(filte: dict):
	"""
	Helper function to send request to DB to delete ride(s) on query `filte`
	Returns if request succeeded or failed
	"""
	payload = {"collection": "rides", "action": 2, "filte": filte}
	res = requests.post(url_db_write, data=dumps(payload), headers=headers).ok
	logger.info(f"DB delete_rides {filte}-> {res}")
	return res


def find_users() -> List[str]:
	"""
	Helper function to send request to DB to find all users
	Returns a list of the usernames of all registered users
	"""
	headers_ = dict(list(headers.items()) + [("Origin", rides_ip)])
	a = requests.get(url_users, headers=headers_)
	res = a.json() if a.status_code != 204 else []
	logger.info(f"DB* find_users -> {res}")
	return res


def next_id():
	"""
	Increments rideId key in redis
	Returns new rideId to be used for inserting a new ride
	"""
	return r.incr("rideId")


class Home(Resource):
	def get(self):
		return {'message': 'Ok. Rides Running'}, 200


class RequestsDB(Resource):
	def get(self) -> List[int]:
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


class Rides(Resource):
	def post(self):
		"""
		summary: endpoint for inserting a ride
		path: /api/v1/rides
		method: post
		requestBody:
			content: application/json
			type: object
			requestBody:
        content: application/json
				type: object
				properties:
					created_by:
						type: string
						description: valid username
					timestamp:
						type: string
						format: 'DD-MM-YYYY:SS-MM-HH'
					source:
						type: integer
						description: valid location id
					destination:
						type: integer
						description: valid location id
			required:
				- created_by
				- timestamp
				- source
				- destination
		responses:
			201: Ride Created
			400: Bad Request. User does not exist or invalid timestamp or invalid location id(s)
		"""
		logger.debug(request.get_json())
		# Fetch request body into a dict-like object
		args = parser.parse_args()
		created_by = args["created_by"]
		timestamp = args["timestamp"]
		source = args["source"]
		destination = args["destination"]

		# Bad Request if user does not exist, or location ids are invalid
		if created_by not in find_users() \
			or source not in locations \
			or destination not in locations \
			or source == destination:
			return {}, 400

		id_ = next_id()

		# Bad Request if timestamp format is invalid
		try:
			timestamp = int(
				datetime.strptime(timestamp, "%d-%m-%Y:%S-%M-%H").timestamp()
			)
		except Exception:
			return {}, 400

		# Bad Request if timestamp is invalid
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

	def get(self) -> List[dict]:
		"""
		summary: endpoint for fetching all rides between `source` and `destination`
		path: /api/v1/rides
		method: get
		parameters:
			- source:
				type: integer
				in: query
				description: Location ID of source
				required: true
			- destination:
				type: integer
				in: query
				description: Location ID of destination
				required: true
		responses:
			200:
				description: OK
				content: application/json
				type: array
				items:
					type: object
					properties:
						rideId:
							type: integer
						username:
							type: string
						timestamp:
							type: string
							format: 'DD-MM-YYYY:SS-MM-HH'
			204:
				description: No Rides between location ids
			400:
				description: Bad Request. Invalid location id(s)
		"""
		# Fetch request arguments into a dict-like object
		args = request.args
		source = int(args["source"])
		destination = int(args["destination"])

		# Bad Request if location ids are invalid
		if source not in locations or destination not in locations:
			return {}, 400

		# build Mongo query for upcoming rides
		query = {
			"source": source,
			"destination": destination,
			"timestamp": {"$gt": int(datetime.now().timestamp())},
		}
		r = find_rides(query)

		# No Content
		if not r:
			return [], 204

		# Format timestamp from UNIX to DD-MM-YYYY:SS-MM-HH
		for r_ in r:
			r_["timestamp"] = datetime.fromtimestamp(r_["timestamp"]).strftime(
				"%d-%m-%Y:%S-%M-%H"
			)

		return r, 200


class RideCount(Resource):
	def get(self) -> List[int]:
		"""
		summary: endpoint for fetching number of rides
		path: /api/v1/rides/count
		method: get
		responses:
			200:
				description: OK
				content: application/json
				type: array
				items:
					type: integer
		"""
		return [len(find_rides({}))], 200


class Ride(Resource):
	def get(self, rideId):
		"""
		summary: endpoint for getting details of ride with `rideId`
		path: /api/v1/rides/
		method: get
		parameters:
			type: integer
			name: rideId
			in: path
			required: true
		responses:
			200:
				description: OK
				content: application/json
				type: object
				properties:
					rideId:
						type: integer
					created_by:
						type: string
					users:
						type: array
						items:
							type: string
					timestamp:
						type: string
						format: 'DD-MM-YYYY:SS-MM-HH'
					source:
						type: integer
					destination:
						type: integer
			400:
				description: Ride ID does not exist
		"""
		# find if rideId exists
		query = {"rideId": rideId}
		r = find_rides(query)

		# Bad Request if rideId does not exist
		if not r:
			return {}, 400

		# Bad Request if ride time has passed
		timestamp = r[0]["timestamp"]
		if timestamp < int(datetime.now().timestamp()):
			return {}, 400

		# Format timestamp from UNIX to DD-MM-YYYY:SS-MM-HH
		r[0]["timestamp"] = datetime.fromtimestamp(timestamp).strftime(
			"%d-%m-%Y:%S-%M-%H"
		)

		return r[0], 200

	def post(self, rideid):
		"""
		summary: endpoint for `username` joining ride with `rideId`
		path: /api/v1/rides/
		method: post
		parameters:
			type: integer
			name: rideId
			in: path
			required: true
		requestBody:
			content: application/json
			type: object
			properties:
				username:
					type: string
		responses:
			200:
				description: Ride Joined
				content: application/json
				type: object
				properties:
					rideId:
						type: integer
					created_by:
						type: string
					users:
						type: array
						items:
							type: string
					timestamp:
						type: string
						format: 'DD-MM-YYYY:SS-MM-HH'
					source:
						type: integer
					destination:
						type: integer
			400:
				description: Username or Ride ID does not exist
		"""
		logger.debug(request.get_json())
		# Fetch request body into a dict-like object
		args = parser.parse_args()
		username = args["username"]

		# find if rideId exists
		query = {"rideId": rideid}
		r = find_rides(query)

		# Bad Request if user does not exist, or ride id does not exist,
		# or user joining ride created by them or user has already joined
		if username not in find_users() \
			or not r \
			or r[0]["created_by"] == username \
			or username in r[0]["users"]:
			return {}, 400

		# add user to joined users
		update_rides({"rideId": rideid}, {"$push": {"users": username}})

		return {}, 200

	def delete(self, rideid):
		"""
		summary: endpoint for deleting ride with `rideId`
		path: /api/v1/rides/
		method: delete
		parameters:
			type: integer
			name: rideId
			in: path
			required: true
		responses:
			200:
				description: Ride deleted
			400:
				description: Ride ID does not exist
		"""
		# find if rideId exists
		query = {"rideId": rideid}

		# Bad request if rideId does not exist
		if not find_rides(query):
			return {}, 400

		# delete if it does
		delete_rides(query)

		return {}, 200


api.add_resource(Home, "/")
api.add_resource(RequestsDB, f"{url_prefix}/_count")
api.add_resource(Rides, f"{url_prefix}/rides")
api.add_resource(Ride, f"{url_prefix}/rides/<int:rideId>")
api.add_resource(RideCount, f"{url_prefix}/rides/count")


if __name__ == "__main__":
	app.run(port=flask_port, host="0.0.0.0", debug=True)
