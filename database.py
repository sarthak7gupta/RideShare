from pymongo import MongoClient

client = MongoClient('localhost', 27017)
db = client['cc_a1']
users_collection = db['users']
rides_collection = db['rides']
counters_collection = db['counters']
