# Design Document: Real-Time Vocabulary Sync

## Overview

The Real-Time Vocabulary Sync feature implements automatic cache invalidation for the AI vocabulary system using PostgreSQL database triggers and Redis Pub/Sub messaging. When vocabulary data changes in Supabase (projects, categories, files), database triggers automatically publish refresh events to Redis, which are consumed by the Python application to update the in-memory cache within 1-2 seconds.

This design leverages existing infrastructure (RedisVocabularyCache, VocabularyLoader) and adds three new components:
1. PostgreSQL trigger function that publishes to Redis via pg_notify
2. Redis listener bridge (external service) that forwards PostgreSQL notifications to Redis Pub/Sub
3. Manual refresh API endpoint for testing and troubleshooting

The system maintains graceful fallback to direct database queries when Redis is unavailable, ensuring vocabulary lookups always work.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Supabase Database                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Project    │  │   Expenses   │  │   CashFlow   │         │
│  │   (trigger)  │  │   (trigger)  │  │   (trigger)  │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                  │
│  ┌──────┴──────────────────┴──────────────────┴──────┐         │
│  │  ExpensesColumn (trigger)  CashFlowColumn (trigger)│         │
│  └──────────────────────┬──────────────────────────────┘        │
│                         │                                        │
│                         ▼                                        │
│              ┌─────────────────────┐                            │
│              │ notify_vocabulary_  │                            │
│              │ change() function   │                            │
│              │ (PostgreSQL NOTIFY) │                            │
│              └──────────┬──────────┘                            │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          │ pg_notify('vocabulary_changed')
                          │
                          ▼
              ┌──────────────────────┐
              │  Redis Listener      │
              │  Bridge Service      │
              │  (Python/Node.js)    │
              └──────────┬───────────┘
                         │
                         │ PUBLISH 'vocabulary_updated'
                         │
                         ▼
              ┌──────────────────────┐
              │    Redis Server      │
              │  (Pub/Sub Channel)   │
              └──────────┬───────────┘
                         │
                         │ SUBSCRIBE 'vocabulary_updated'
                         │
                         ▼
              ┌──────────────────────────┐
              │  FastAPI Application     │
              │  ┌────────────────────┐  │
              │  │ RedisVocabulary    │  │
              │  │ Cache (Listener)   │  │
              │  └─────────┬──────────┘  │
              │            │              │
              │            ▼              │
              │  ┌────────────────────┐  │
              │  │ VocabularyLoader   │  │
              │  │ (Database Query)   │  │
              │  └────────────────────┘  │
              └──────────────────────────┘
```

### Data Flow

1. **Database Change**: User adds/updates/deletes vocabulary data in Supabase
2. **Trigger Execution**: PostgreSQL trigger fires and calls `notify_vocabulary_change()`
3. **PostgreSQL NOTIFY**: Function sends notification via `pg_notify('vocabulary_changed', table_name)`
4. **Bridge Service**: External listener receives pg_notify and publishes to Redis Pub/Sub
5. **Redis Pub/Sub**: Message published to 'vocabulary_updated' channel
6. **Cache Listener**: RedisVocabularyCache receives event in background thread
7. **Cache Refresh**: VocabularyLoader queries database and updates Redis cache
8. **AI Query**: Next AI query uses updated vocabulary for entity matching

### Alternative Approach: Direct Redis Integration

**Note**: PostgreSQL cannot directly publish to Redis. We need a bridge service that:
- Listens to PostgreSQL NOTIFY events using `LISTEN vocabulary_changed`
- Publishes received events to Redis Pub/Sub channel

This bridge can be implemented as:
- **Option A**: Separate Python script using `psycopg2` with `LISTEN/NOTIFY`
- **Option B**: Node.js service using `pg` library
- **Option C**: Supabase Edge Function (if supported)

For this design, we'll use **Option A** (Python script) for consistency with the existing codebase.

## Components and Interfaces

### 1. Database Trigger Function

**File**: `supabase/migrations/YYYYMMDD_vocabulary_sync_triggers.sql`

```sql
-- Function that sends notification when vocabulary changes
CREATE OR REPLACE FUNCTION notify_vocabulary_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Send notification with table name as payload
    PERFORM pg_notify('vocabulary_changed', TG_TABLE_NAME);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers on all vocabulary tables
CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "Project"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "Expenses"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "CashFlow"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "ExpensesColumn"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();

CREATE TRIGGER vocabulary_change_trigger
AFTER INSERT OR UPDATE OR DELETE ON "CashFlowColumn"
FOR EACH STATEMENT
EXECUTE FUNCTION notify_vocabulary_change();
```

**Key Design Decisions**:
- Use `FOR EACH STATEMENT` instead of `FOR EACH ROW` to avoid duplicate notifications on bulk operations
- Use `pg_notify` instead of direct Redis connection (PostgreSQL limitation)
- Include table name in payload for debugging and potential future filtering
- Use `AFTER` trigger to ensure transaction is committed before notification

### 2. Redis Listener Bridge Service

**File**: `app/services/vocabulary_sync_bridge.py`

```python
"""
PostgreSQL to Redis Bridge for Vocabulary Sync
Listens to PostgreSQL NOTIFY events and forwards to Redis Pub/Sub
"""

import psycopg2
import redis
import select
import time
from app.config import Config
from app.utils.logger import logger


class VocabularySyncBridge:
    """
    Bridge service that listens to PostgreSQL NOTIFY events
    and publishes them to Redis Pub/Sub channel.
    """
    
    def __init__(self):
        self.pg_conn = None
        self.redis_client = None
        self.running = False
    
    def connect(self):
        """Establish connections to PostgreSQL and Redis."""
        # PostgreSQL connection
        pg_url = f"{Config.SUPABASE_URL}/db"  # Adjust based on Supabase connection string
        self.pg_conn = psycopg2.connect(
            host=Config.SUPABASE_HOST,
            port=Config.SUPABASE_PORT,
            database=Config.SUPABASE_DB,
            user=Config.SUPABASE_USER,
            password=Config.SUPABASE_PASSWORD
        )
        self.pg_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Redis connection
        self.redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            decode_responses=True
        )
        
        logger.success("Bridge connected to PostgreSQL and Redis")
    
    def start(self):
        """Start listening for PostgreSQL notifications."""
        self.running = True
        cursor = self.pg_conn.cursor()
        cursor.execute("LISTEN vocabulary_changed;")
        
        logger.info("Bridge listening for vocabulary changes...")
        
        while self.running:
            # Wait for notification with 5 second timeout
            if select.select([self.pg_conn], [], [], 5) == ([], [], []):
                continue
            
            self.pg_conn.poll()
            
            while self.pg_conn.notifies:
                notify = self.pg_conn.notifies.pop(0)
                table_name = notify.payload
                
                logger.info(f"Vocabulary change detected: {table_name}")
                
                # Publish to Redis Pub/Sub
                self.redis_client.publish('vocabulary_updated', table_name)
                logger.success(f"Published to Redis: vocabulary_updated ({table_name})")
    
    def stop(self):
        """Stop the bridge service."""
        self.running = False
        if self.pg_conn:
            self.pg_conn.close()
        logger.info("Bridge stopped")


def run_bridge():
    """Main entry point for bridge service."""
    bridge = VocabularySyncBridge()
    
    try:
        bridge.connect()
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Bridge interrupted by user")
        bridge.stop()
    except Exception as e:
        logger.error(f"Bridge error: {e}")
        bridge.stop()


if __name__ == "__main__":
    run_bridge()
```

**Key Design Decisions**:
- Use `psycopg2` for PostgreSQL LISTEN/NOTIFY support
- Use `select.select()` for non-blocking notification polling
- Run as separate process (not part of FastAPI app) for isolation
- Include graceful shutdown handling
- Log all events for debugging

### 3. Manual Refresh API Endpoint

**File**: `app/api/routes/vocabulary.py` (new file)

```python
"""
Vocabulary Management API Endpoints
"""

from fastapi import APIRouter, HTTPException
from app.services.redis_vocabulary import redis_vocabulary_cache
from app.utils.logger import logger


router = APIRouter(prefix="/api/vocabulary", tags=["Vocabulary"])


@router.post("/refresh")
async def refresh_vocabulary():
    """
    Manually trigger vocabulary cache refresh.
    
    Use this endpoint for:
    - Testing cache refresh functionality
    - Troubleshooting cache sync issues
    - Forcing immediate update after bulk data imports
    
    Returns:
        Success message with vocabulary counts
    """
    try:
        logger.info("Manual vocabulary refresh triggered via API")
        
        # Trigger refresh
        redis_vocabulary_cache.refresh_cache()
        
        # Get updated vocabulary for response
        vocab = redis_vocabulary_cache.get_vocabulary()
        
        return {
            "success": True,
            "message": "Vocabulary cache refreshed successfully",
            "vocabulary_counts": {
                "projects": len(vocab.get('projects', [])),
                "expense_categories": len(vocab.get('expense_categories', [])),
                "cashflow_categories": len(vocab.get('cashflow_categories', [])),
                "expense_files": len(vocab.get('expense_files', [])),
                "cashflow_files": len(vocab.get('cashflow_files', []))
            }
        }
    
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh vocabulary cache: {str(e)}"
        )
```

**Key Design Decisions**:
- Use POST method (refresh is a state-changing operation)
- Return vocabulary counts for verification
- Include detailed error messages for troubleshooting
- Log all manual refresh operations

### 4. Application Startup Integration

**File**: `app/main.py` (modifications)

```python
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting AU-Ggregates AI API Server...")
    
    # Start Redis listener for real-time vocabulary updates
    try:
        from app.services.redis_vocabulary import redis_vocabulary_cache
        redis_vocabulary_cache.start_listener()
        
        # Initial cache refresh
        redis_vocabulary_cache.refresh_cache()
        logger.success("Redis vocabulary cache initialized")
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        logger.info("Falling back to vocabulary_loader (no real-time updates)")
    
    # ... existing startup code ...
```

**Key Design Decisions**:
- Initialize Redis listener before other services
- Perform initial cache refresh to populate cache
- Gracefully handle Redis connection failures
- Log all initialization steps

### 5. Configuration Updates

**File**: `app/config.py` (additions)

```python
class Config:
    # ... existing config ...
    
    # PostgreSQL Configuration (for bridge service)
    SUPABASE_HOST: str = os.getenv("SUPABASE_HOST", "")
    SUPABASE_PORT: int = int(os.getenv("SUPABASE_PORT", "5432"))
    SUPABASE_DB: str = os.getenv("SUPABASE_DB", "postgres")
    SUPABASE_USER: str = os.getenv("SUPABASE_USER", "")
    SUPABASE_PASSWORD: str = os.getenv("SUPABASE_PASSWORD", "")
```

**Environment Variables** (`.env` additions):

```bash
# PostgreSQL Direct Connection (for bridge service)
SUPABASE_HOST=db.your-project.supabase.co
SUPABASE_PORT=5432
SUPABASE_DB=postgres
SUPABASE_USER=postgres
SUPABASE_PASSWORD=your-password
```

## Data Models

### Vocabulary Data Structure

The vocabulary cache stores data in the following JSON structure:

```json
{
  "projects": ["Hanapin", "Fuel", "Marikina", ...],
  "project_locations": ["Quezon City", "Manila", ...],
  "expense_files": ["2024-01-expenses.xlsx", ...],
  "cashflow_files": ["2024-01-cashflow.xlsx", ...],
  "expense_categories": ["Transportation", "Materials", ...],
  "cashflow_categories": ["Revenue", "Operating Expenses", ...]
}
```

### Redis Data Storage

**Key**: `vocabulary`  
**Type**: String (JSON serialized)  
**TTL**: 3600 seconds (1 hour backup expiration)

### PostgreSQL Notification Payload

**Channel**: `vocabulary_changed`  
**Payload**: Table name (e.g., "Project", "Expenses", "CashFlow", "ExpensesColumn", "CashFlowColumn")

### Redis Pub/Sub Message

**Channel**: `vocabulary_updated`  
**Message**: Table name (forwarded from PostgreSQL notification)


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Database triggers publish notifications for all operations

*For any* vocabulary table (Project, Expenses, CashFlow, ExpensesColumn, CashFlowColumn) and any database operation (INSERT, UPDATE, DELETE), when the operation completes, a notification should be published to the 'vocabulary_changed' channel with the table name as payload.

**Validates: Requirements 1.1, 1.2, 1.3, 1.5**

### Property 2: Cache refresh completes within time bound

*For any* vocabulary update event, when the RedisVocabularyCache detects the event, the cache refresh should complete within 5 seconds and the updated vocabulary should be available in Redis.

**Validates: Requirements 2.1, 8.1**

### Property 3: Cache refresh updates all vocabulary data

*For any* cache refresh operation, when vocabulary is reloaded from the database and stored in Redis, the cached data should include all six vocabulary fields (projects, project_locations, expense_files, cashflow_files, expense_categories, cashflow_categories) and the system should log the operation with vocabulary counts.

**Validates: Requirements 2.2, 2.3, 2.4, 7.1, 7.2, 7.3, 7.4, 7.5**

### Property 4: Fallback mode provides accurate vocabulary data

*For any* vocabulary query, when Redis is unavailable or connection fails, the system should fallback to VocabularyLoader and return the same vocabulary data that would be returned if Redis were available.

**Validates: Requirements 3.2, 3.3, 3.4**

### Property 5: Redis reconnection after failure

*For any* cache operation, when Redis was previously unavailable but has become available again, the system should successfully reconnect and use Redis for caching.

**Validates: Requirements 3.5**

### Property 6: Manual refresh endpoint triggers cache update

*For any* HTTP POST request to /api/vocabulary/refresh, when the request is processed, the system should trigger a cache refresh, log the manual refresh operation, and return HTTP 200 with vocabulary counts on success or HTTP 500 with error message on failure.

**Validates: Requirements 4.2, 4.3, 4.4, 4.5**

### Property 7: Listener initialization and subscription

*For any* RedisVocabularyCache initialization, when the cache is initialized, the system should start the listener thread and subscribe to the 'vocabulary_updated' Redis channel.

**Validates: Requirements 5.2, 5.3**

### Property 8: Trigger function includes table name in payload

*For any* database trigger execution, when the trigger fires, the notification payload should contain the name of the table that triggered the event.

**Validates: Requirements 6.4**

### Property 9: Trigger function handles errors gracefully

*For any* database operation on a vocabulary table, when the trigger function encounters an error, the original database operation should still complete successfully without being blocked.

**Validates: Requirements 6.5**

### Property 10: Listener crash fallback behavior

*For any* Redis listener thread crash, when the crash occurs, the system should log the error and continue serving vocabulary requests using VocabularyLoader fallback mode.

**Validates: Requirements 8.3**

## Error Handling

### Database Trigger Errors

**Scenario**: Trigger function fails to send notification  
**Handling**: Use PostgreSQL exception handling to catch errors and allow the database operation to complete. Log errors to PostgreSQL logs but don't raise exceptions that would rollback the transaction.

```sql
CREATE OR REPLACE FUNCTION notify_vocabulary_change()
RETURNS TRIGGER AS $$
BEGIN
    BEGIN
        PERFORM pg_notify('vocabulary_changed', TG_TABLE_NAME);
    EXCEPTION WHEN OTHERS THEN
        -- Log error but don't block the operation
        RAISE WARNING 'Failed to notify vocabulary change: %', SQLERRM;
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Bridge Service Errors

**Scenario**: Bridge service loses connection to PostgreSQL or Redis  
**Handling**: Implement automatic reconnection with exponential backoff. Log connection errors and retry every 5, 10, 20, 40 seconds up to a maximum of 5 minutes.

**Scenario**: Bridge service crashes  
**Handling**: Use process manager (systemd, supervisor, or Docker restart policy) to automatically restart the service. The system continues working via fallback mode until bridge recovers.

### Redis Connection Errors

**Scenario**: Redis is unavailable at startup  
**Handling**: Log warning and set `redis_available = False`. All vocabulary queries fallback to VocabularyLoader. Application continues normal operation.

**Scenario**: Redis connection fails during operation  
**Handling**: Catch `redis.ConnectionError` and `redis.TimeoutError` exceptions. Log error and fallback to VocabularyLoader for that specific request. Next request will attempt to reconnect.

### Cache Refresh Errors

**Scenario**: Database query fails during cache refresh  
**Handling**: Catch exception, log error with details, and keep existing cache data. Return cached data if available, otherwise fallback to direct database query.

**Scenario**: Redis write fails during cache refresh  
**Handling**: Catch exception, log error, and continue operation. Next request will trigger cache refresh again.

### API Endpoint Errors

**Scenario**: Manual refresh endpoint called when Redis is unavailable  
**Handling**: Return HTTP 500 with error message explaining Redis is unavailable. Suggest checking Redis connection.

**Scenario**: Manual refresh endpoint called during ongoing refresh  
**Handling**: Allow concurrent refresh (Redis handles concurrent writes). Return success when refresh completes.

## Testing Strategy

### Unit Tests

Unit tests verify specific examples, edge cases, and error conditions:

1. **Trigger Installation Verification**
   - Verify triggers exist on all five vocabulary tables
   - Verify trigger timing is AFTER INSERT OR UPDATE OR DELETE
   - Verify trigger function exists and has correct signature

2. **API Endpoint Tests**
   - Test POST /api/vocabulary/refresh returns 200 on success
   - Test endpoint returns vocabulary counts in response
   - Test endpoint returns 500 when Redis is unavailable
   - Test endpoint logs manual refresh operations

3. **Startup Initialization Tests**
   - Test RedisVocabularyCache initializes on startup
   - Test listener thread starts on initialization
   - Test initial cache refresh occurs on startup
   - Test graceful handling when Redis is unavailable at startup

4. **Configuration Tests**
   - Test cache TTL is set to 3600 seconds
   - Test Redis connection parameters are loaded from config
   - Test PostgreSQL connection parameters are loaded for bridge

5. **Error Handling Tests**
   - Test fallback to VocabularyLoader when Redis is unavailable
   - Test warning logged when Redis connection fails at startup
   - Test trigger function doesn't block database operations on error

### Property-Based Tests

Property-based tests verify universal properties across all inputs. Each test should run a minimum of 100 iterations.

1. **Property Test: Database triggers publish notifications**
   - Generate random vocabulary data (projects, categories, files)
   - Insert/update/delete data in random vocabulary tables
   - Verify notification is published to 'vocabulary_changed' channel
   - Verify notification payload contains correct table name
   - **Tag**: Feature: real-time-vocabulary-sync, Property 1: Database triggers publish notifications for all operations

2. **Property Test: Cache refresh updates all vocabulary data**
   - Generate random vocabulary data across all six fields
   - Trigger cache refresh
   - Verify Redis cache contains all six vocabulary fields
   - Verify cached data matches database data
   - Verify log contains vocabulary counts
   - **Tag**: Feature: real-time-vocabulary-sync, Property 3: Cache refresh updates all vocabulary data

3. **Property Test: Fallback mode provides accurate vocabulary data**
   - Generate random vocabulary queries
   - Disable Redis connection
   - Query vocabulary using fallback mode
   - Enable Redis and query again
   - Verify both queries return identical vocabulary data
   - **Tag**: Feature: real-time-vocabulary-sync, Property 4: Fallback mode provides accurate vocabulary data

4. **Property Test: Manual refresh endpoint triggers cache update**
   - Generate random vocabulary data
   - Add data to database
   - Call POST /api/vocabulary/refresh
   - Verify response is HTTP 200
   - Verify response contains vocabulary counts
   - Verify Redis cache contains new data
   - Verify log contains manual refresh entry
   - **Tag**: Feature: real-time-vocabulary-sync, Property 6: Manual refresh endpoint triggers cache update

5. **Property Test: Listener initialization and subscription**
   - Initialize RedisVocabularyCache multiple times with random configurations
   - Verify listener thread is started each time
   - Verify subscription to 'vocabulary_updated' channel exists
   - Publish test message and verify listener receives it
   - **Tag**: Feature: real-time-vocabulary-sync, Property 7: Listener initialization and subscription

6. **Property Test: Trigger function includes table name in payload**
   - For each vocabulary table, perform random INSERT/UPDATE/DELETE
   - Capture notification payload
   - Verify payload contains the correct table name
   - **Tag**: Feature: real-time-vocabulary-sync, Property 8: Trigger function includes table name in payload

7. **Property Test: Trigger function handles errors gracefully**
   - Simulate trigger function errors (e.g., Redis unavailable)
   - Perform random database operations on vocabulary tables
   - Verify database operations complete successfully
   - Verify data is correctly inserted/updated/deleted despite trigger errors
   - **Tag**: Feature: real-time-vocabulary-sync, Property 9: Trigger function handles errors gracefully

8. **Property Test: Redis reconnection after failure**
   - Start with Redis available
   - Perform vocabulary query (should use Redis)
   - Disable Redis
   - Perform vocabulary query (should use fallback)
   - Re-enable Redis
   - Perform vocabulary query (should reconnect and use Redis)
   - Verify all queries return correct vocabulary data
   - **Tag**: Feature: real-time-vocabulary-sync, Property 5: Redis reconnection after failure

### Integration Tests

Integration tests verify end-to-end workflows:

1. **End-to-End Vocabulary Sync Test**
   - Start application with Redis and bridge service running
   - Insert new project into database
   - Wait up to 2 seconds
   - Query vocabulary via AI system
   - Verify new project is detected in vocabulary
   - Verify cache was refreshed (check logs)

2. **Multi-Server Cache Sync Test**
   - Start two FastAPI instances connected to same Redis
   - Insert vocabulary data via one instance
   - Query vocabulary via second instance
   - Verify both instances see the same updated vocabulary

3. **Bridge Service Recovery Test**
   - Start system with bridge service running
   - Kill bridge service process
   - Insert vocabulary data (should not trigger cache refresh)
   - Restart bridge service
   - Insert more vocabulary data
   - Verify cache refresh occurs after bridge recovery

### Performance Tests

1. **Cache Refresh Performance**
   - Load 1000+ projects, 500+ categories, 200+ files
   - Trigger cache refresh
   - Verify refresh completes within 5 seconds
   - Measure memory usage during refresh

2. **Concurrent Refresh Handling**
   - Trigger 10 simultaneous cache refreshes
   - Verify all complete successfully
   - Verify no race conditions or data corruption
   - Verify final cache state is consistent

3. **Listener Latency Test**
   - Insert vocabulary data
   - Measure time from database commit to cache refresh completion
   - Verify latency is under 2 seconds for 95th percentile

## Deployment Considerations

### Bridge Service Deployment

The bridge service must run as a separate process alongside the FastAPI application:

**Option 1: Systemd Service (Linux)**
```ini
[Unit]
Description=Vocabulary Sync Bridge
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=app
WorkingDirectory=/app
ExecStart=/usr/bin/python3 -m app.services.vocabulary_sync_bridge
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Option 2: Docker Compose**
```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - bridge
  
  bridge:
    build: .
    command: python -m app.services.vocabulary_sync_bridge
    depends_on:
      - redis
    environment:
      - SUPABASE_HOST=${SUPABASE_HOST}
      - REDIS_HOST=redis
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**Option 3: Supervisor**
```ini
[program:vocabulary_bridge]
command=/usr/bin/python3 -m app.services.vocabulary_sync_bridge
directory=/app
autostart=true
autorestart=true
stderr_logfile=/var/log/vocabulary_bridge.err.log
stdout_logfile=/var/log/vocabulary_bridge.out.log
```

### Database Migration Deployment

1. Create migration file: `supabase/migrations/YYYYMMDD_vocabulary_sync_triggers.sql`
2. Apply migration via Supabase CLI: `supabase db push`
3. Verify triggers installed: Query `pg_trigger` table
4. Test trigger execution: Insert test data and verify notification

### Redis Deployment

For production, use managed Redis service (AWS ElastiCache, Redis Cloud, etc.) or deploy Redis with:
- Persistence enabled (AOF or RDB)
- Replication for high availability
- Monitoring and alerting
- Backup strategy

### Monitoring and Alerting

**Metrics to Monitor**:
- Cache refresh latency (should be < 2 seconds)
- Cache hit rate (should be > 95%)
- Bridge service uptime
- Redis connection errors
- Trigger execution count
- Fallback mode usage

**Alerts to Configure**:
- Bridge service down for > 5 minutes
- Redis unavailable for > 5 minutes
- Cache refresh latency > 5 seconds
- High fallback mode usage (> 10% of requests)
- Trigger execution failures

### Rollback Plan

If issues occur after deployment:

1. **Disable Triggers**: Drop triggers from vocabulary tables to stop notifications
2. **Stop Bridge Service**: Prevent Redis Pub/Sub messages
3. **System Continues**: Application works via fallback mode (direct database queries)
4. **Investigate**: Review logs, fix issues
5. **Re-enable**: Recreate triggers and restart bridge service

The system is designed to gracefully degrade, so rollback doesn't cause downtime.
