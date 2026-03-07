FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 9010

CMD ["uvicorn", "app:APP", "--host", "0.0.0.0", "--port", "9010"]
