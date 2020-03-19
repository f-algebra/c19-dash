FROM tiangolo/uwsgi-nginx-flask:python3.7
COPY ./uwsgi.ini /app/uwsgi.ini
COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY ./src /app
