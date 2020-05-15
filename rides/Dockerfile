FROM python:3.7

EXPOSE 5000

RUN mkdir -p /rides
WORKDIR /rides

COPY requirements.txt .

RUN python -m pip install -r requirements.txt

COPY . .

CMD ["/usr/local/bin/gunicorn", "wsgi:app", "-c", "gunicorn.config.py"]
