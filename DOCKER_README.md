# ED3Hub Docker Setup

This guide explains how to run the ED3Hub platform using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose installed on your system

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/wisteen/ed3hub.git
cd ed3hub
```

### 2. Set up environment variables
Create a `.env` file in the `Backend` directory with your credentials:
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email
EMAIL_HOST=your-email-host
EMAIL_PORT=587
EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-email-password
```

### 3. Build and run with Docker Compose
```bash
docker-compose up --build
```

This will:
- Build the Backend (Django) container
- Build the Frontend (Next.js) container
- Start both services
- Backend will be available at http://localhost:8000
- Frontend will be available at http://localhost:3000

### 4. Run in detached mode
```bash
docker-compose up -d
```

## Individual Service Commands

### Build Backend only
```bash
docker build -t ed3hub-backend ./Backend
```

### Build Frontend only
```bash
docker build -t ed3hub-frontend ./Frontend
```

### Run Backend only
```bash
docker run -p 8000:8000 --env-file ./Backend/.env ed3hub-backend
```

### Run Frontend only
```bash
docker run -p 3000:3000 ed3hub-frontend
```

## Docker Compose Commands

### Start services
```bash
docker-compose up
```

### Stop services
```bash
docker-compose down
```

### View logs
```bash
docker-compose logs -f
```

### Restart services
```bash
docker-compose restart
```

### Remove volumes (clean slate)
```bash
docker-compose down -v
```

## Accessing the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin

## Troubleshooting

### Port already in use
If ports 3000 or 8000 are already in use, modify the port mappings in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

### Database migrations
To run migrations manually:
```bash
docker-compose exec backend python manage.py migrate
```

### Create superuser
```bash
docker-compose exec backend python manage.py createsuperuser
```

### Install new dependencies
After adding new packages, rebuild the containers:
```bash
docker-compose up --build
```

## Production Deployment

For production, consider:
1. Using PostgreSQL instead of SQLite
2. Setting `DEBUG=False` in environment variables
3. Configuring proper `ALLOWED_HOSTS`
4. Using a reverse proxy (Nginx)
5. Setting up SSL certificates
6. Using environment-specific docker-compose files

## Architecture

```
┌─────────────────┐
│   Frontend      │
│   (Next.js)     │
│   Port: 3000    │
└────────┬────────┘
         │
         │ HTTP
         │
┌────────▼────────┐
│   Backend       │
│   (Django)      │
│   Port: 8000    │
└─────────────────┘
```
