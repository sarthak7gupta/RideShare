from collections import namedtuple

inter = namedtuple("inter", ["docker", "extern"])
micro = namedtuple("ports", ["users", "rides"])

flask_ports = inter(docker=5000, extern=80)

flask_ips = inter(
	docker="localhost", extern="CC-1638425011.us-east-1.elb.amazonaws.com"
)

db_ports = micro(users=27017, rides=27017)

db_ips = micro(users="mongousers", rides="mongorides")
