from pymongo import MongoClient


def reset():
	client = MongoClient('localhost', 27017)
	db = client['cc_a1']
	db['users'].delete_many({})
	db['rides'].delete_many({})
	db['counters'].delete_many({})
	db['counters'].insert_one({'_id': 'rideid', 'sequence_value': 0})
	print('Reset!')


if __name__ == "__main__":
	reset()
