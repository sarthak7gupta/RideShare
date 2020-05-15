from pymongo import MongoClient

from config import db_ips as ips
from config import db_ports as ports

client = MongoClient(ips.users, ports.users)
db = client["cc"]
users_collection = db["users"]
counters_collection = db["counters"]
