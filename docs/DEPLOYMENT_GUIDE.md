# Deployment Guide: 3-Stage AI Query System

**Production Deployment Instructions**

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Model Installation](#model-installation)
4. [Database Setup](#database-setup)
5. [Application Configuration](#application-configuration)
6. [Deployment Options](#deployment-options)
7. [Health Checks](#health-checks)
8. [Monitoring](#monitoring)
9. [Rollback Plan](#rollback-plan)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 4 cores
- RAM: 8GB
- Storage: 10GB free space
- OS: Windows 10/11, Linux (Ubuntu 20.04+), macOS 11+

**Recommended**:
- CPU: 8 cores
- RAM: 16GB
- Storage: 20GB free space
- GPU: NVIDIA GPU with 4GB+ VRAM (optional, for faster inference)

### Software Requirements

- Python 3.9 or higher
- PostgreSQL 13+ (or Supabase)
- Git
- pip or conda

---

## Environment Setup

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd <project-directory>
```

### Step 2: Create Virtual Environment

**Windows**:
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac**:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies**:
- `torch==2.1.0` - PyTorch for model inference
- `transformers==4.36.0` - Hugging Face Transformers
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `supabase` - Database client

---

## Model Installation

### Option 1: Download Pre-trained Models

```bash
# Run model download script
python scripts/download_models.py
```

This will download:
- T5 Text-to-SQL model (~242MB)
- Enhanced DistilBERT Orchestrator (~250MB)

### Option 2: Manual Installation

1. **T5 Model**:
   - Download from Google Drive (link provided separately)
   - Extract to `ml/models/t5_text_to_sql/`

2. **DistilBERT Model**:
   - Download from Google Drive (link provided separately)
   - Extract to `ml/models/enhanced_orchestrator_model/`

### Verify Installation

```bash
python scripts/verify_installation.py
```

Expected output:
```
✅ T5 model found
✅ DistilBERT model found
✅ All dependencies installed
✅ System ready for deployment
```

---

## Database Setup

### Supabase Configuration

1. **Create Supabase Project**:
   - Go to https://supabase.com
   - Create new project
   - Note down project URL and API key

2. **Run Migrations**:
   ```bash
   # Apply database schema
   psql -h <supabase-host> -U postgres -d postgres -f supabase/migrations/20260126_init_ai_search.sql
   ```

3. **Verify Tables**:
   ```sql
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public';
   ```

   Expected tables:
   - `ai_documents`
   - `projects`
   - `conversations`

---

## Application Configuration

### Step 1: Create .env File

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### Step 2: Configure Environment Variables

Edit `.env`:

```env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# T5 Configuration
TEXT_TO_SQL_USE_T5=true
T5_MODEL_PATH=ml/models/t5_text_to_sql
T5_CONFIDENCE_THRESHOLD=0.7

# Orchestrator Configuration
ORCHESTRATOR_ENABLED=true
ORCHESTRATOR_MODEL_PATH=ml/models/enhanced_orchestrator_model

# DB Clarification
DB_CLARIFICATION_ENABLED=true
DB_CLARIFICATION_MAX_OPTIONS=10

# Security
ALLOWED_TABLES=ai_documents,projects,conversations
SQL_GUARDRAILS_ENABLED=true

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

### Step 3: Validate Configuration

```bash
python -c "from app.config import settings; print('Config loaded successfully')"
```

---

## Deployment Options

### Option 1: Local Development

```bash
# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access at: http://localhost:8000

### Option 2: Production (Uvicorn)

```bash
# Start with multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Option 3: Docker Deployment

**Create Dockerfile**:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Download models (if not included)
RUN python scripts/download_models.py

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Build and Run**:
```bash
# Build image
docker build -t ai-query-system .

# Run container
docker run -d -p 8000:8000 --env-file .env ai-query-system
```

### Option 4: Docker Compose

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./ml/models:/app/ml/models
    restart: unless-stopped
```

**Run**:
```bash
docker-compose up -d
```

---

## Health Checks

### Endpoint Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "t5_model": "loaded",
  "orchestrator": "loaded",
  "database": "connected"
}
```

### Model Loading Check

```bash
curl http://localhost:8000/api/status
```

Expected response:
```json
{
  "t5_available": true,
  "orchestrator_available": true,
  "guardrails_enabled": true
}
```

### Database Connection Check

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "org_id": 1, "user_id": "test"}'
```

---

## Monitoring

### Application Logs

**View Logs**:
```bash
# Development
tail -f logs/app_$(date +%Y-%m-%d).log

# Docker
docker logs -f <container-id>
```

### Performance Metrics

Monitor these metrics:
- **Stage 1 Latency**: Target <50ms, Actual 70-85ms
- **Stage 2 Latency**: Target <200ms, Actual ~2.6s (CPU)
- **Total Pipeline**: Target <500ms, Actual ~2.8s (CPU)
- **Memory Usage**: Monitor RAM consumption
- **CPU Usage**: Monitor CPU utilization

### Error Tracking

Check error logs:
```bash
tail -f logs/errors_$(date +%Y-%m-%d).log
```

Common errors:
- Model loading failures
- Database connection issues
- SQL guardrail rejections

---

## Rollback Plan

### Scenario 1: Model Issues

**Symptoms**: Low accuracy, high error rate

**Rollback**:
1. Disable T5 model:
   ```env
   TEXT_TO_SQL_USE_T5=false
   ```
2. System falls back to Universal Handler
3. Restart application

### Scenario 2: Database Issues

**Symptoms**: Connection errors, slow queries

**Rollback**:
1. Check database connection
2. Verify Supabase status
3. Restore from backup if needed

### Scenario 3: Complete Rollback

**Steps**:
1. Stop current deployment:
   ```bash
   docker-compose down
   # or
   pkill -f uvicorn
   ```

2. Checkout previous version:
   ```bash
   git checkout <previous-commit>
   ```

3. Redeploy:
   ```bash
   docker-compose up -d
   # or
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

---

## Troubleshooting

### Issue: Models Not Loading

**Symptoms**:
```
FileNotFoundError: Model files not found
```

**Solution**:
1. Verify model files exist:
   ```bash
   ls ml/models/t5_text_to_sql/
   ls ml/models/enhanced_orchestrator_model/
   ```
2. Re-download models:
   ```bash
   python scripts/download_models.py
   ```

### Issue: Slow Performance

**Symptoms**: Queries taking >5 seconds

**Solution**:
1. Check CPU usage: `top` or Task Manager
2. Enable GPU if available:
   ```python
   # In config.py
   DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
   ```
3. Consider model quantization

### Issue: Database Connection Failed

**Symptoms**:
```
ConnectionError: Could not connect to database
```

**Solution**:
1. Verify Supabase credentials in `.env`
2. Check network connectivity
3. Verify Supabase project is active

### Issue: SQL Guardrails Blocking Valid Queries

**Symptoms**: Legitimate queries rejected

**Solution**:
1. Check allowed tables in `.env`:
   ```env
   ALLOWED_TABLES=ai_documents,projects,conversations,<new_table>
   ```
2. Restart application

### Issue: High Memory Usage

**Symptoms**: RAM usage >8GB

**Solution**:
1. Reduce number of workers:
   ```bash
   uvicorn app.main:app --workers 2
   ```
2. Enable model quantization
3. Increase server RAM

---

## Production Checklist

Before deploying to production:

- [ ] All models downloaded and verified
- [ ] Database migrations applied
- [ ] `.env` file configured with production values
- [ ] Health checks passing
- [ ] All tests passing (28 unit tests)
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Rollback plan documented
- [ ] Security review completed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Team trained on new system

---

## Security Best Practices

1. **Environment Variables**:
   - Never commit `.env` to version control
   - Use secrets management (AWS Secrets Manager, Azure Key Vault)

2. **Database**:
   - Use service role key for backend operations
   - Enable Row Level Security (RLS) in Supabase
   - Regular backups

3. **API**:
   - Enable CORS restrictions
   - Add rate limiting
   - Use HTTPS in production

4. **Models**:
   - Verify model checksums
   - Store models securely
   - Regular security audits

---

## Performance Optimization

### GPU Acceleration

If GPU available:
```python
# In app/config.py
import torch
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
```

Expected speedup:
- Stage 2 T5: 2.6s → 200-300ms (10x faster)

### Model Quantization

Reduce model size and improve speed:
```python
# Quantize T5 model
from transformers import T5ForConditionalGeneration
model = T5ForConditionalGeneration.from_pretrained(
    "ml/models/t5_text_to_sql",
    load_in_8bit=True  # 8-bit quantization
)
```

### Caching

Cache common queries:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def generate_sql(query: str):
    # ... SQL generation logic
    pass
```

---

## Support

For issues or questions:
- Check logs: `logs/app_*.log` and `logs/errors_*.log`
- Review documentation: `docs/`
- Contact: [support email]

---

**Last Updated**: February 15, 2026  
**Version**: 1.0  
**Author**: Kiro AI Assistant
