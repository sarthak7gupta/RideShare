from pymongo import MongoClient

from config import db_ips as ips
from config import db_ports as ports

client = MongoClient(ips.rides, ports.rides)
db = client["cc"]
rides_collection = db["rides"]
counters_collection = db["counters"]
