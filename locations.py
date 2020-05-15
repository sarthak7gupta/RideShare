with open("AreaNameEnum.csv", "r") as f:
	locations = {
		int(area_no): area_name
		for area_no, area_name in [
			line.split(",") for line in f.read().splitlines()[1:]
		]
	}

if __name__ == "__main__":
	print(locations)
