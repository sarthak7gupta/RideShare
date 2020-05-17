"""
	RideShare (Cloud Computing Project)
	main.py: python file containing the orchestrator API logic
"""

from json import dumps, loads
from typing import Any, List

from flask import Flask, request
from flask_restful import Api, Resource, reqparse

from utils import (ReadRpcClient, incr_redis_count, kill_slave, logger,
                   push_to_Q, scale_after, worker_pids)

# Flask RESTful Setup
app = Flask(__name__)
api = Api(app)

# Paths for API endpoints
url_prefix = "/api/v1"
db_url_prefix = f"{url_prefix}/db"
crash_url_prefix = f"{url_prefix}/crash"
worker_url_prefix = f"{url_prefix}/worker"

# Defining arguments used by REST endpoints in JSON body
parser = reqparse.RequestParser()
parser.add_argument("collection", type=str)
parser.add_argument("action", type=int)
parser.add_argument("document", type=dict)
parser.add_argument("filte", type=dict)
parser.add_argument("update", type=dict)


@app.before_first_request
def start_daemon():
	"""
	Start autoscale timer right after the first request is received.
	"""
	# Autoscale the slave containers based on the requests every 2 minutes.
	scale_after(interval=120)


class DBRead(Resource):
	def post(self) -> Any:
		"""
		summary: endpoint for DB read operations
		description: returns documents from `collection` on query `filte`
		path: /api/v1/db/read
		method: post
		requestBody:
			content: application/json
			type: object
			arguments:
				collection:
					type: string
				filte:
					type: object
			required:
				- collection
				- filte
		responses:
			200:
				description: OK
				content: application/json
				type: any
			400:
				description: Bad Request
		"""
		# Increase Read API request count in Redis
		incr_redis_count()
		logger.debug(request.get_json())
		# Fetch request body into a dict-like object
		args = parser.parse_args()
		# Build query to be sent to DB Worker
		query = dumps({"collection": args["collection"], "filte": args["filte"]})
		# Send query to readQ, and fetch the result sent back to respQ
		resp = ReadRpcClient().call(query)
		# Return response as a python object
		return loads(resp), 200


class DBWrite(Resource):
	def post(self) -> dict:
		"""
		summary: endpoint for DB write operations
		description:
			- on `action` = 0, inserts `document` into `collection`
			- on `action` = 1, performs `update` on all documents from `collection` where query `filte`
			- on `action` = 2, deletes all documents from `collection` where query `filte`
		path: /api/v1/db/write
		method: post
		requestBody:
			content: application/json
			type: object
			arguments:
				collection:
					type: string
				action:
					type: int
					enum:
						- 0
						- 1
						- 2
				filte:
					type: object
				document:
					type: object
				update:
					type: object
				filte:
					type: object
			required:
				- colllection
				- action
		responses:
			201: Write Performed
			400: Bad Request
		"""
		logger.debug(request.get_json())
		# Fetch request body into a dict-like object
		args = parser.parse_args()
		# Build query to be sent to DB Worker
		query = dumps(args)
		# Send query to writeQ
		push_to_Q("writeQ", query)
		return {}, 201


class DBClear(Resource):
	def post(self) -> dict:
		"""
		summary: endpoint for DB clear operations
		description:
			clears the users and rides collections from the database
		path: /api/v1/db/clear
		method: post
		response:
			200: OK
		"""
		# Build queries to be sent to DB Worker
		query_rides = dumps({"collection": "rides", "action": 2, "filte": {}})
		query_users = dumps({"collection": "users", "action": 2, "filte": {}})
		# Send queries to writeQ
		push_to_Q("writeQ", query_rides)
		push_to_Q("writeQ", query_users)
		return {}, 200


class CrashSlave(Resource):
	def post(self) -> List[int]:
		"""
		summary: endpoint to crash the slave with highest PID
		description: returns the PID of the slave killed
		path: /api/v1/crash/slave
		method: post
		response:
			200:
				description: OK
				content: application/json
				type: array
				items:
					type: integer
		"""
		return [kill_slave()], 200


class Worker(Resource):
	def get(self) -> List[int]:
		"""
		summary: endpoint to array all the PIDs of all workers
		description: returns a sorted array of all PIDs of the slave
		path: /api/v1/worker/list
		method: get
		response:
			200:
				description: OK
				content: application/json
				type: array
				items:
					type: integer
		"""
		return worker_pids(), 200


api.add_resource(DBRead, f"{db_url_prefix}/read")
api.add_resource(DBWrite, f"{db_url_prefix}/write")
api.add_resource(DBClear, f"{db_url_prefix}/clear")
api.add_resource(CrashSlave, f"{crash_url_prefix}/slave")
api.add_resource(Worker, f"{worker_url_prefix}/list")


if __name__ == "__main__":
	app.run(debug=True, use_reloader=False)
