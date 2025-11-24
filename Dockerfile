FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Verificar instalación de Chrome
RUN google-chrome --version

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY app.py .

# Crear usuario no-root para seguridad
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Exponer puerto (Render usa 10000)
EXPOSE 10000

# Variables de entorno para Render
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV PORT=10000

# Comando para ejecutar la aplicación (optimizado para Render)
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "120", "--worker-class", "sync", "--max-requests", "100", "app:app"]