# Untestables API

The Untestables API provides a RESTful interface for managing GitHub repository scanning tasks.

## Running the API

### Local Development
```bash
# Install dependencies
poetry install

# Run database migrations
poetry run alembic upgrade head

# Start the API server
poetry run uvicorn untestables.api.main:app --reload

# Or use the poetry script
poetry run api
```

### Docker
```bash
# Build and run with docker-compose
docker-compose up api

# The API will be available at http://localhost:8000
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Get Current Gaps
```bash
GET /gaps?min_size=100&limit=10
```

### Create Scan Task
```bash
POST /scan/range
{
  "min_stars": 100,
  "max_stars": 200,
  "force_rescan": false,
  "rescan_days": 7
}
```

### List Tasks
```bash
GET /tasks?status=pending&limit=10
```

### Get Task Status
```bash
GET /tasks/{task_id}
```

### Cancel Task
```bash
POST /tasks/{task_id}/cancel
```

### Get Repository Statistics
```bash
GET /stats/repositories
```

### Start Orchestration
```bash
POST /orchestrate/start
{
  "duration_hours": 24
}
```

## Example Usage

### Using curl

1. Start a scan for repositories with 1000-2000 stars:
```bash
curl -X POST http://localhost:8000/scan/range \
  -H "Content-Type: application/json" \
  -d '{"min_stars": 1000, "max_stars": 2000}'
```

2. Check the status of a task:
```bash
curl http://localhost:8000/tasks/{task_id}
```

3. Get current gaps in coverage:
```bash
curl http://localhost:8000/gaps
```

4. Start orchestration for 24 hours:
```bash
curl -X POST http://localhost:8000/orchestrate/start \
  -H "Content-Type: application/json" \
  -d '{"duration_hours": 24}'
```

### Using Python

```python
import requests

# Create a scan task
response = requests.post(
    "http://localhost:8000/scan/range",
    json={"min_stars": 100, "max_stars": 200}
)
task = response.json()
print(f"Task created: {task['id']}")

# Check task status
response = requests.get(f"http://localhost:8000/tasks/{task['id']}")
status = response.json()
print(f"Status: {status['status']}")

# Get gaps
response = requests.get("http://localhost:8000/gaps")
gaps = response.json()
for gap in gaps:
    print(f"Gap: {gap['min_stars']}-{gap['max_stars']} (size: {gap['size']})")
```

## Task States

- `pending`: Task created but not started
- `running`: Task is currently executing
- `completed`: Task finished successfully
- `failed`: Task failed with an error
- `cancelled`: Task was cancelled

## Background Processing

The API uses FastAPI's background tasks to execute scans asynchronously. Tasks are tracked in the PostgreSQL database, providing persistence across API restarts.

## Monitoring

- Check `/health` for API and database status
- Use `/tasks` to monitor active and completed tasks
- View `/stats/repositories` for scanning progress