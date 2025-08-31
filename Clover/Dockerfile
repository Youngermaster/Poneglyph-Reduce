FROM python:3.11-slim
WORKDIR /app
COPY . /app
ENV MASTER=http://master:8080
CMD ["python", "submit_job.py"]
