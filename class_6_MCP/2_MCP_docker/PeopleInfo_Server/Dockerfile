FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py employee_data.csv ./

ENV PYTHONUNBUFFERED=1
ENV TRANSPORT=sse
ENV HOST=0.0.0.0
ENV PORT=8001

EXPOSE 8001

ENTRYPOINT ["python", "server.py"]
CMD ["--transport", "sse", "--host", "0.0.0.0", "--port", "8001"]
