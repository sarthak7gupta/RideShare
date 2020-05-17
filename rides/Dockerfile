FROM python

RUN mkdir -p /rides
WORKDIR /rides

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt

COPY . .

CMD /usr/local/bin/gunicorn wsgi:app -c gunicorn.config.py
