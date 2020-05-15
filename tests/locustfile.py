from json import dumps
from random import choices, choice
from datetime import datetime

from locust import HttpLocust, TaskSet, between, task
from names import get_full_name

from services import reset

"locust --host=http://localhost:80 --locustfile locustfile.py --no-web -c 100 -r 10 --print-stats --run-time 3m"

prefix = "/api/v1"

users = []


class RideShareTasks(TaskSet):
	@task
	def add_user(self):
		url = f"{prefix}/users"
		username = get_full_name()
		users.append(username)
		payload = {
			"username": username,
			"password": "".join(choices("abcdef0123456789", k=40)),
		}
		headers = {"Content-Type": "application/json"}
		r = self.client.put(url, data=dumps(payload), headers=headers)
		print(r.status_code)

	@task
	def create_ride(self):
		url = f"{prefix}/rides"
		payload = {
			"created_by": choice(users),
			"timestamp": datetime.now().strftime("%d-%m-%Y:%S-%M-%H"),
			"source": choice(range(1, 200)),
			"destination": choice(range(1, 200)),
		}
		headers = {"Content-Type": "application/json"}
		r = self.client.post(url, data=dumps(payload), headers=headers)
		print(r.status_code)

	@task
	def list_rides(self):
		url = f"{prefix}/rides?source={choice(range(1, 200))}&destination={choice(range(1, 200))}"
		r = self.client.get(url)
		print(r.status_code)

	@task
	def ride_details(self):
		url = f"{prefix}/rides/{choice(range(1, 200))}"
		r = self.client.get(url)
		print(r.status_code)

	@task
	def join_ride(self):
		url = f"{prefix}/rides/{choice(range(1, 200))}"
		payload = {"username": choice(users)}
		headers = {"Content-Type": "application/json"}
		r = self.client.post(url, data=dumps(payload), headers=headers)
		print(r.status_code)


class WebsiteUser(HttpLocust):
	task_set = RideShareTasks
	wait_time = between(5, 15)
