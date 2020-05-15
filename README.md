# CloudComputing

cd RideShare
. venv/bin/activate
sudo venv/bin/gunicorn wsgi:app -c gunicorn.config.py
