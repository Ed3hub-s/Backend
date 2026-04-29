FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create media and static directories
RUN mkdir -p media staticfiles static/img

# Expose port
EXPOSE 8000

# Run migrations, create superuser, collect static, then start server
CMD python manage.py migrate && \
    python manage.py create_superuser_env && \
    python manage.py collectstatic --noinput && \
    daphne -b 0.0.0.0 -p 8000 core.asgi:application
