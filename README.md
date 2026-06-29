# ED3Hub Backend

Django REST API powering the ED3Hub decentralized education platform.

## Features

- JWT authentication with Google OAuth & OTP verification
- Course management (modules, lessons, quizzes, assessments)
- Live session scheduling & registration
- Automated PDF certificate generation
- Token reward system (blockchain-ready)
- Real-time chat & notifications via Django Channels (WebSocket)

## Prerequisites

- Python 3.11+
- pip

## Setup

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Create a `.env` file in this directory:

```env
SECRET_KEY=your-secret-key
DEBUG=True

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API available at: **http://localhost:8000**
Admin panel: **http://localhost:8000/admin**
API docs (Swagger): **http://localhost:8000/swagger/**

## Scheduled Newsletters Without Redis/Celery

Celery beat can still send scheduled newsletters when Redis is running. If Redis or Celery is unavailable, run the database-backed scheduler instead:

```bash
python manage.py send_due_newsletters --loop --interval 600
```

For cron or Windows Task Scheduler, run it once every 5-10 minutes instead:

```bash
python manage.py send_due_newsletters
```

## Docker

```bash
docker-compose up --build
```

See [DOCKER_README.md](DOCKER_README.md) and [DOCKER_SETUP_GUIDE_WINDOWS.md](DOCKER_SETUP_GUIDE_WINDOWS.md) for details.

## Project Structure

```
Backend/
├── authentication/     # User auth, profiles, OTP
├── courses/            # Courses, modules, lessons, quizzes, certificates, sessions
├── chat/               # Real-time messaging (WebSocket)
├── notifications/      # Real-time notifications
├── core/               # Django settings, ASGI/WSGI, Celery
├── templates/          # Email templates
├── media/              # Uploaded files
├── manage.py
├── requirements.txt
└── Dockerfile
```

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register user |
| POST | `/api/auth/login/` | Login |
| POST | `/api/auth/verify-otp/` | OTP verification |
| POST | `/api/auth/token/refresh/` | Refresh JWT |
| GET/POST | `/api/courses/` | List / create courses |
| GET | `/api/courses/{id}/content/` | Course modules & lessons |
| POST | `/api/courses/sessions/{id}/register/` | Register for session |
| POST | `/api/courses/certificates/issue/` | Issue certificate |

Full docs: **http://localhost:8000/swagger/**

## Additional Docs

- [Course Upload Details](README_COURSE_UPLOAD.md)
- [Notification System](NOTIFICATION_SYSTEM_ANALYSIS.md)
- [Real-time Chat Setup](REALTIME_CHAT_SETUP_COMPLETE.md)
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)

## Deployment

1. Set `DEBUG=False`
2. Configure `ALLOWED_HOSTS`
3. Switch to PostgreSQL
4. Serve static/media via AWS S3 or Cloudinary
5. Use Gunicorn: `gunicorn core.wsgi:application`
6. Configure HTTPS

See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) for the full checklist.

## Testing

```bash
python manage.py test
```
