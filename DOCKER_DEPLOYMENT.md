# Academic Management System - Docker Deployment Guide

## Prerequisites
- Docker installed on your system
- Docker Compose installed

## Quick Start

### 1. Build and Run with Docker Compose
```bash
# Build and start the application
docker-compose up --build

# Run in background
docker-compose up -d --build
```

### 2. Access the Application
Open your browser and go to: `http://localhost:5000`

### 3. Stop the Application
```bash
docker-compose down
```

## Manual Docker Commands

### Build the Image
```bash
docker build -t academic-management-system .
```

### Run the Container
```bash
docker run -d \
  --name academic-management \
  -p 5000:5000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/instance:/app/instance \
  academic-management-system
```

### View Logs
```bash
docker logs academic-management
```

### Stop and Remove Container
```bash
docker stop academic-management
docker rm academic-management
```

## Environment Variables

You can customize the following environment variables:

- `FLASK_APP`: Application entry point (default: app.py)
- `FLASK_ENV`: Environment mode (default: production)
- `SECRET_KEY`: Flask secret key for sessions

## Volumes

The following directories are mounted as volumes:
- `./uploads`: For file uploads
- `./logs`: For application logs
- `./instance`: For database and instance files

## Production Deployment

### 1. Update Environment Variables
Edit `docker-compose.yml` and set a strong `SECRET_KEY`:
```yaml
environment:
  - SECRET_KEY=your-very-secure-secret-key-here
```

### 2. Use a Reverse Proxy
For production, it's recommended to use a reverse proxy like Nginx:
```yaml
# Add to docker-compose.yml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
  depends_on:
    - academic-management
```

### 3. Database Configuration
For production, consider using PostgreSQL instead of SQLite:
1. Uncomment the postgres service in `docker-compose.yml`
2. Update your application to use PostgreSQL
3. Set appropriate database environment variables

## Troubleshooting

### Check Container Status
```bash
docker ps
docker-compose ps
```

### View Application Logs
```bash
docker logs academic-management-system
```

### Access Container Shell
```bash
docker exec -it academic-management-system bash
```

### Rebuild After Code Changes
```bash
docker-compose down
docker-compose up --build
```

## Security Notes

1. Change the default `SECRET_KEY` in production
2. Use HTTPS in production
3. Regularly update Docker images
4. Monitor application logs
5. Backup your database regularly

## Performance Optimization

1. Use multi-stage builds for smaller images
2. Implement caching strategies
3. Use a production WSGI server like Gunicorn
4. Consider using a CDN for static files 