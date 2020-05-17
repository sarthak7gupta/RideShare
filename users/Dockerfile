FROM python

EXPOSE 5000

RUN mkdir -p /users
WORKDIR /users

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt

COPY . .

CMD /usr/local/bin/gunicorn wsgi:app -c gunicorn.config.py
