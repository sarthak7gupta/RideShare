from os import popen

rmq_host = "rabbitmq"  # hostname of RMQ container
mongodb_host: str = popen("hostname").read().strip()  # find your hostname
# mongodb_host = "worker-master"
