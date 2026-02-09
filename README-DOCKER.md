# 🐳 Agent Autopsy Docker Deployment

This guide shows how to deploy the Agent Autopsy application using Docker.

## 📋 Prerequisites

- Docker and Docker Compose installed
- Access to Langfuse credentials
- (Optional) External database for persistence

## 🚀 Quick Start

### 1. Environment Setup

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```bash
# Required: Langfuse credentials
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Optional: LLM for explanations
LLM_ENABLED=false
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3

# Application settings
DEBUG=false
LOG_LEVEL=INFO
```

### 2. Build and Run

Using Docker Compose (recommended):

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

Using Docker directly:

```bash
# Build the image
docker build -t agent-autopsy .

# Run the container
docker run -d \
  --name agent-autopsy \
  -p 8000:8000 \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/reports:/app/reports \
  agent-autopsy
```

## 🌐 Accessing the Application

- **API Documentation**: http://localhost:8000/docs
- **Streamlit UI**: http://localhost:8501
- **Health Check**: http://localhost:8000/health

## 📁 Directory Structure

```
├── Dockerfile              # Main Docker configuration
├── docker-compose.yml      # Multi-service orchestration
├── docker-entrypoint.sh    # Container startup script
├── .env.example           # Environment variables template
├── .dockerignore          # Files to exclude from build
├── agent_autopsy/         # Backend API code
├── client_app/           # Streamlit UI code
└── reports/              # Generated reports (mounted volume)
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `STREAMLIT_HOST` | `0.0.0.0` | Streamlit host |
| `STREAMLIT_PORT` | `8501` | Streamlit port |
| `LANGFUSE_PUBLIC_KEY` | - | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | - | Langfuse secret key |
| `LANGFUSE_BASE_URL` | - | Langfuse base URL |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |

### Volumes

- `/app/reports`: Persistent storage for generated reports
- `/app/logs`: Application logs

## 🏥 Health Checks

The container includes health checks that monitor:

- API server responsiveness
- Container resource usage
- Service availability

Check health status:

```bash
docker ps
# Look for "healthy" status

# Or check directly
curl http://localhost:8000/health
```

## 📊 Monitoring

### Logs

View application logs:

```bash
# Docker Compose
docker-compose logs -f agent-autopsy

# Docker
docker logs -f agent-autopsy
```

### Metrics

The application exposes health endpoints for monitoring:

- `/health` - Basic health check
- `/metrics` - Application metrics (if configured)

## 🔒 Security

### Environment Variables

- Never commit `.env` to version control
- Use Docker secrets or Kubernetes secrets in production
- Rotate API keys regularly

### Network Security

- Only expose necessary ports (8000, 8501)
- Use reverse proxy (nginx/traefik) in production
- Enable HTTPS/TLS termination

## 🚀 Production Deployment

### Using Docker Compose

```yaml
# production-docker-compose.yml
version: '3.8'
services:
  agent-autopsy:
    image: agent-autopsy:latest
    restart: always
    environment:
      - DEBUG=false
      - LOG_LEVEL=WARNING
    volumes:
      - ./reports:/app/reports
      - ./logs:/app/logs
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.autopsy.rule=Host(`autopsy.yourdomain.com`)"
      - "traefik.http.routers.autopsy.tls=true"
```

### Using Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-autopsy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent-autopsy
  template:
    metadata:
      labels:
        app: agent-autopsy
    spec:
      containers:
      - name: agent-autopsy
        image: agent-autopsy:latest
        ports:
        - containerPort: 8000
        - containerPort: 8501
        env:
        - name: LANGFUSE_PUBLIC_KEY
          valueFrom:
            secretKeyRef:
              name: langfuse-secrets
              key: public-key
```

## 🛠️ Troubleshooting

### Common Issues

1. **Container fails to start**
   ```bash
   # Check logs
   docker logs agent-autopsy
   
   # Verify environment variables
   docker-compose config
   ```

2. **API not responding**
   ```bash
   # Check if API is running
   curl http://localhost:8000/health
   
   # Restart container
   docker-compose restart agent-autopsy
   ```

3. **Permission issues with reports**
   ```bash
   # Fix permissions
   sudo chown -R 1000:1000 reports/
   ```

### Debug Mode

Enable debug logging:

```bash
# Set in .env
DEBUG=true
LOG_LEVEL=DEBUG

# Or override with docker-compose
docker-compose run -e DEBUG=true agent-autopsy
```

## 🔄 Updates

### Updating the Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up -d --build

# Or pull new image
docker-compose pull
docker-compose up -d
```

### Backup Data

```bash
# Backup reports
docker run --rm -v $(pwd)/reports:/data -v $(pwd)/backup:/backup alpine tar czf /backup/reports-$(date +%Y%m%d).tar.gz -C /data .

# Restore reports
docker run --rm -v $(pwd)/reports:/data -v $(pwd)/backup:/backup alpine tar xzf /backup/reports-20231201.tar.gz -C /data
```

## 📞 Support

For issues with Docker deployment:

1. Check the logs: `docker-compose logs -f`
2. Verify environment variables: `docker-compose config`
3. Test health endpoint: `curl http://localhost:8000/health`
4. Review this documentation

## 🏷️ Tags and Versions

- `latest`: Latest stable release
- `v1.0.0`: Specific version tags
- `develop`: Development build

Pull specific versions:

```bash
docker pull agent-autopsy:v1.0.0
docker pull agent-autopsy:latest
```
