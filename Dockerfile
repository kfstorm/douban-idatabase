FROM python:3.11.8-alpine3.19

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY app/* /app/
COPY run.sh /run.sh

EXPOSE 8000

ENTRYPOINT [ "/run.sh" ]
