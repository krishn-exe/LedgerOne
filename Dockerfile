FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY App ./App
WORKDIR /app/App/Backend

EXPOSE 8000

CMD ["sh", "-c", "python ../Database/setup.py && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
