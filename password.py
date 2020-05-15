from hashlib import sha1
from re import search


def generateSHA(password: str):
	return sha1(password.encode()).hexdigest()


def isValidSHA(password: str):
	return bool(search("[A-Fa-f0-9]{40}", password))


if __name__ == "__main__":
	print(isValidSHA(generateSHA("12345678")))
