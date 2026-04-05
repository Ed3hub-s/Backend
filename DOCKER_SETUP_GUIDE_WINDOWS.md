# Docker Setup Guide for Windows - ED3Hub

## 📋 Prerequisites Check

### 1. Verify Docker Desktop is Installed

Open **PowerShell** or **Command Prompt** and run:

```bash
docker --version
docker-compose --version
```

You should see something like:
```
Docker version 24.0.x
Docker Compose version v2.x.x
```

If you see these, Docker is installed! ✅

If not, download from: https://www.docker.com/products/docker-desktop/

---

## 🚀 Step-by-Step Setup

### Step 1: Open Docker Desktop

1. Click **Start Menu**
2. Search for **Docker Desktop**
3. Click to open it
4. Wait for Docker to start (you'll see a whale icon in system tray)
5. Make sure it says **"Docker Desktop is running"**

---

### Step 2: Navigate to Project Directory

Open **PowerShell** or **Command Prompt**:

```bash
# Navigate to your project
cd C:\Users\HomePC\Downloads\ed3hub
```

---

### Step 3: Install Backend Dependencies First

Before running Docker, we need to install the new packages:

```bash
# Navigate to Backend
cd Backend

# Install new dependencies
pip install channels==4.0.0 channels-redis==4.1.0 daphne==4.0.0 celery==5.3.4 redis==5.0.1
```

---

### Step 4: Create Database Migrations

Still in the Backend directory:

```bash
# Create migrations for notifications app
python manage.py makemigrations notifications

# Apply all migrations
python manage.py migrate
```

You should see:
```
Migrations for 'notifications':
  notifications\migrations\0001_initial.py
    - Create model Notification
    - Create model NotificationPreference
```

---

### Step 5: Build Docker Images

Go back to the root directory:

```bash
# Go back to root
cd ..

# Build all Docker images (this will take 5-10 minutes first time)
docker-compose build
```

You'll see:
```
Building backend...
Building frontend...
Building celery...
Building celery-beat...
```

---

### Step 6: Start All Services

```bash
# Start all services
docker-compose up
```

You should see logs from:
- ✅ **redis** - Message broker
- ✅ **backend** - Django API (port 8000)
- ✅ **celery** - Background tasks
- ✅ **celery-beat** - Scheduled tasks
- ✅ **frontend** - Next.js app (port 3000)

**Wait until you see:**
```
backend    | Daphne running on 0.0.0.0:8000
frontend   | Ready on http://localhost:3000
```

---

### Step 7: Access the Application

Open your browser:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **API Docs**: http://localhost:8000/api/docs/

---

## 🛠️ Common Docker Commands

### Start Services (Detached Mode - Runs in Background)

```bash
docker-compose up -d
```

### Stop Services

```bash
docker-compose down
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f redis
docker-compose logs -f celery
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart frontend
```

### Rebuild After Code Changes

```bash
# Rebuild and restart
docker-compose up --build
```

### Check Running Containers

```bash
docker-compose ps
```

You should see:
```
NAME                STATUS              PORTS
ed3hub-backend      Up                  0.0.0.0:8000->8000/tcp
ed3hub-frontend     Up                  0.0.0.0:3000->3000/tcp
ed3hub-redis        Up                  0.0.0.0:6379->6379/tcp
ed3hub-celery       Up
ed3hub-celery-beat  Up
```

### Stop and Remove Everything

```bash
# Stop and remove containers, networks
docker-compose down

# Stop and remove containers, networks, AND volumes (clean slate)
docker-compose down -v
```

---

## 🐛 Troubleshooting

### Problem 1: "Port 8000 is already in use"

**Solution**: Stop any running Django server

```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

Or change port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Use 8001 instead
```

---

### Problem 2: "Port 3000 is already in use"

**Solution**: Stop any running Next.js server

```bash
# Find process using port 3000
netstat -ano | findstr :3000

# Kill the process
taskkill /PID <PID> /F
```

---

### Problem 3: Docker Desktop Not Starting

**Solution**:

1. Open **Task Manager** (Ctrl + Shift + Esc)
2. Go to **Services** tab
3. Find **com.docker.service**
4. Right-click → **Start**

Or restart Docker Desktop:
1. Right-click Docker icon in system tray
2. Click **Quit Docker Desktop**
3. Start Docker Desktop again

---

### Problem 4: "No module named 'channels'"

**Solution**: Rebuild Docker images

```bash
docker-compose build --no-cache
docker-compose up
```

---

### Problem 5: Database Errors

**Solution**: Run migrations inside Docker container

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser
```

---

### Problem 6: Frontend Build Errors

**Solution**: Clear Next.js cache

```bash
# Stop containers
docker-compose down

# Remove frontend container
docker-compose rm frontend

# Rebuild
docker-compose up --build frontend
```

---

### Problem 7: Redis Connection Error

**Solution**: Make sure Redis is running

```bash
# Check Redis status
docker-compose ps redis

# Restart Redis
docker-compose restart redis

# Check Redis logs
docker-compose logs redis
```

---

## 📊 Verify Everything is Working

### 1. Check Backend

Open browser: http://localhost:8000

You should see the API landing page.

### 2. Check Frontend

Open browser: http://localhost:3000

You should see the ED3Hub homepage.

### 3. Check Redis

```bash
docker-compose exec redis redis-cli ping
```

Should return: `PONG`

### 4. Check Celery

```bash
docker-compose logs celery
```

Should see: `celery@... ready`

### 5. Check WebSocket (Notifications)

Open browser console on http://localhost:3000 and check for:
```
WebSocket connected
```

### 6. Check WebSocket (Chat)

Navigate to a chat page and check console for:
```
Chat WebSocket connected
```

---

## 🔄 Development Workflow

### Making Code Changes

#### Backend Changes:

1. Edit Python files in `Backend/`
2. Save the file
3. Docker will auto-reload (if using volumes)
4. Or restart: `docker-compose restart backend`

#### Frontend Changes:

1. Edit files in `Frontend/src/`
2. Save the file
3. Next.js will auto-reload (hot reload)
4. Changes appear immediately in browser

#### Database Changes:

```bash
# Create new migration
docker-compose exec backend python manage.py makemigrations

# Apply migration
docker-compose exec backend python manage.py migrate
```

#### Install New Package:

**Backend**:
```bash
# Add to requirements.txt
echo "new-package==1.0.0" >> Backend/requirements.txt

# Rebuild
docker-compose build backend
docker-compose up -d backend
```

**Frontend**:
```bash
# Add to package.json or run inside container
docker-compose exec frontend npm install new-package

# Or rebuild
docker-compose build frontend
docker-compose up -d frontend
```

---

## 📁 Docker Files Overview

### docker-compose.yml
Main configuration file that defines all services:
- **redis**: Message broker
- **backend**: Django API
- **celery**: Background worker
- **celery-beat**: Scheduler
- **frontend**: Next.js app

### Backend/Dockerfile
Defines how to build the Backend container:
- Python 3.11
- Install dependencies
- Run Daphne ASGI server

### Frontend/Dockerfile
Defines how to build the Frontend container:
- Node.js 20
- Install dependencies
- Build Next.js app
- Run production server

---

## 🎯 Quick Start Commands

### First Time Setup:

```bash
# 1. Navigate to project
cd C:\Users\HomePC\Downloads\ed3hub

# 2. Install backend dependencies
cd Backend
pip install channels==4.0.0 channels-redis==4.1.0 daphne==4.0.0 celery==5.3.4 redis==5.0.1

# 3. Create migrations
python manage.py makemigrations notifications
python manage.py migrate

# 4. Go back to root
cd ..

# 5. Build Docker images
docker-compose build

# 6. Start services
docker-compose up
```

### Daily Development:

```bash
# Start
docker-compose up

# Or start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## 🔍 Monitoring

### View All Container Status:

```bash
docker-compose ps
```

### View Resource Usage:

```bash
docker stats
```

### View Logs in Real-Time:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

### Execute Commands Inside Container:

```bash
# Backend shell
docker-compose exec backend bash

# Python shell
docker-compose exec backend python manage.py shell

# Frontend shell
docker-compose exec frontend sh
```

---

## 🧹 Cleanup

### Remove Stopped Containers:

```bash
docker-compose rm
```

### Remove All Containers and Networks:

```bash
docker-compose down
```

### Remove Everything Including Volumes:

```bash
docker-compose down -v
```

### Remove Unused Images:

```bash
docker image prune -a
```

### Complete Cleanup (Free Space):

```bash
# Remove everything
docker-compose down -v
docker system prune -a --volumes

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up
```

---

## 📞 Getting Help

### Check Docker Desktop Dashboard:

1. Open Docker Desktop
2. Click **Containers** tab
3. See all running containers
4. Click on a container to see logs
5. Click **CLI** button to open terminal inside container

### Check Logs:

```bash
# Backend logs
docker-compose logs backend

# Frontend logs
docker-compose logs frontend

# All logs
docker-compose logs
```

### Common Issues:

1. **Port conflicts**: Change ports in docker-compose.yml
2. **Build errors**: Run `docker-compose build --no-cache`
3. **Database errors**: Run migrations inside container
4. **Redis errors**: Restart redis service
5. **Permission errors**: Run Docker Desktop as Administrator

---

## ✅ Success Checklist

After running `docker-compose up`, verify:

- [ ] Docker Desktop is running
- [ ] 5 containers are running (redis, backend, celery, celery-beat, frontend)
- [ ] http://localhost:8000 shows API landing page
- [ ] http://localhost:3000 shows ED3Hub homepage
- [ ] No error messages in logs
- [ ] WebSocket connections working (check browser console)

---

## 🎉 You're Ready!

Your ED3Hub platform is now running with:
- ✅ Real-time notifications
- ✅ Real-time chat
- ✅ Background tasks (Celery)
- ✅ Scheduled reminders (Celery Beat)
- ✅ Redis message broker
- ✅ WebSocket support

**Access your app at: http://localhost:3000**

---

## 📚 Additional Resources

- Docker Documentation: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/
- Django Channels: https://channels.readthedocs.io/
- Celery: https://docs.celeryproject.org/

---

**Need help? Check the logs first: `docker-compose logs -f`**
