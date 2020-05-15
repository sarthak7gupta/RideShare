from collections import namedtuple

inter = namedtuple("inter", ["docker", "extern"])
micro = namedtuple("ports", ["users", "rides"])

flask_ports = inter(
	docker=micro(users=5000, rides=5000), extern=micro(users=8080, rides=8000)
)

flask_ips = inter(
	docker=micro(users="localhost", rides="localhost"),
	extern=micro(users="users", rides="rides"),
)

db_ports = inter(
	docker=micro(users=27017, rides=27017), extern=micro(users=27020, rides=27021)
)

db_ips = inter(
	docker=micro(users="localhost", rides="localhost"),
	extern=micro(users="mongousers", rides="mongorides"),
)

if __name__ == "__main__":
	print(
		flask_ports.docker.users,
		flask_ports.docker.rides,
		flask_ports.extern.users,
		flask_ports.extern.rides,
		sep="\n",
	)
	print(
		flask_ips.docker.users,
		flask_ips.docker.rides,
		flask_ips.extern.users,
		flask_ips.extern.rides,
		sep="\n",
	)
