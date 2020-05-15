for i in {`seq 1 7`}; do
	python services.py;
	py.test api"$i".tavern.yaml;
done
