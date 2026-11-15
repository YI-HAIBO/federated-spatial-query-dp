FROM python:3.14-slim
WORKDIR /app
COPY node.py /app/node.py
COPY measure.py /app/measure.py
COPY ready.py /app/ready.py
EXPOSE 8000
CMD ["python3", "/app/node.py"]
