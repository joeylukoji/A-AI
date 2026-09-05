FROM python:3.12-slim
WORKDIR /app
# fonts-dejavu-core : libellés de pièces accentués (Séjour, Véranda, m²) nets dans le rendu vectoriel
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV AI_STUB=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
