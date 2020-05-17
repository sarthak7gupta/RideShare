FROM ubuntu

RUN mkdir -p /slave
WORKDIR /slave

RUN apt update
RUN apt install -y python3 python3-pip
RUN apt install -y mongodb

RUN mkdir -p /data/db

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt

COPY . .

CMD sleep 20 && python3 main.py 1
