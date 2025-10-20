# app/Dockerfile

FROM python:3.9-slim

WORKDIR /app/app-viwer

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \    
    git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Fabioaugustmp/ml-politicas-energeticas-ifg-2025.git .

RUN pip3 install -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]