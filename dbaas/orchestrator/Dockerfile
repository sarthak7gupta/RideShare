FROM python

RUN mkdir -p /orchestrator
WORKDIR /orchestrator

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt

COPY . .

CMD sleep 20 && /usr/local/bin/gunicorn wsgi:app -c gunicorn.config.py
