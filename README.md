# Douban iDatabase

A FastAPI-based web API service that aggregates movie/TV metadata from multiple sources including Douban, IMDB, TMDB, and TVDB. Features comprehensive data collection, caching, background processing, and API management with rate limiting and monitoring.

## Features

- **Multi-Source Aggregation**: Combines data from Douban, IMDB, TMDB, and TVDB
- **ID Translation**: Convert between different ID systems (Douban ID ↔ IMDB ID ↔ TMDB ID ↔ TVDB ID)
- **Background Processing**: Queue-based system for continuous data discovery and updates
- **Rate Limiting**: Per-user and IP-based rate limiting with Redis support
- **Caching**: Multi-level caching with Redis for external API responses
- **Metrics**: Prometheus metrics for monitoring and observability
- **Automated Discovery**: Scheduled tasks for sitemap crawling, list discovery, tag exploration

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (optional, for caching and rate limiting)
- UV package manager (recommended)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd douban-idatabase

# Initialize the repository
./scripts/init_repo.sh

# Or manually with UV
uv sync --all-extras
```

### Running the Application

```bash
# Start the API server with background scheduler
./run.sh

# Or directly with Python
python -m app.main
```

The API will be available at `http://localhost:8000`

### Docker Deployment

```bash
# Build the Docker image
docker build -t douban-idatabase .

# Run with environment variables
docker run -p 8000:8000 \
  -e REDIS_URL=redis://host:6379/0 \
  -e TMDB_API_KEY=your_tmdb_key \
  douban-idatabase
```

## API Usage

### Authentication

API access requires an API key passed via header or query parameter:

```bash
# Via header
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/item?douban_id=12345

# Via query parameter
curl http://localhost:8000/api/item?douban_id=12345&api_key=your_api_key
```

### Query Items

```bash
# Query by Douban ID
curl http://localhost:8000/api/item?douban_id=1292052

# Query by IMDB ID
curl http://localhost:8000/api/item?imdb_id=tt0137523

# Query by Douban title (exact match)
curl http://localhost:8000/api/item?douban_title=千与千寻

# Query by TMDB ID (requires media type)
curl http://localhost:8000/api/item?tmdb_id=129&tmdb_media_type=movie

# Query by TVDB ID
curl http://localhost:8000/api/item?tvdb_id=81189
```

### Response Format

```json
[
  {
    "douban_id": "1292052",
    "imdb_id": "tt0245429",
    "douban_title": "千与千寻",
    "year": 2001,
    "rating": 9.4,
    "update_time": 1704067200.0
  }
]
```

### Metrics Endpoint (Admin Only)

```bash
curl -H "X-API-Key: admin_api_key" http://localhost:8000/metrics
```

## Configuration

Configuration is managed via environment variables or `.env` file:

### Database & Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLALCHEMY_DATABASE_URL` | `sqlite:///db.sqlite3` | SQLite database path |
| `REDIS_URL` | `""` | Redis connection URL |

### External APIs

| Variable | Description |
|----------|-------------|
| `TMDB_API_KEY` | TMDB API key for ID translation |
| `ZENROWS_API_KEY` | ZenRows proxy service API key |
| `DOUBAN_COOKIE_DBCL2` | Douban authentication cookie |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOW_ANONYMOUS_API_ACCESS` | `false` | Enable access without API key |
| `ANONYMOUS_RATE_LIMIT` | 1000 | Requests per window for anonymous users |
| `ANONYMOUS_WINDOW_SIZE` | 3600 | Time window in seconds |

### Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `QUEUE_PROCESSOR_THREAD_COUNT` | 4 | Background worker threads |
| `QUEUE_PROCESS_TIME_LIMIT_SECONDS` | 360 | Max processing time per batch |
| `DISABLE_SCHEDULER` | `false` | Disable background scheduler |
| `DISABLED_TASK_TYPES` | See config.py | Comma-separated list of disabled tasks |

### Refresh Intervals

| Variable | Default | Description |
|----------|---------|-------------|
| `ITEM_REFRESH_INTERVAL_DEFAULT_DAYS` | 30 | Default refresh interval |
| `ITEM_REFRESH_INTERVAL_MAX_DAYS` | 365 | Maximum refresh interval |
| `LIST_REFRESH_MIN_INTERVAL_DAYS` | 30 | List refresh minimum interval |
| `TAG_REFRESH_INTERVAL_DAYS` | 30 | Tag refresh interval |

See `app/config.py` for the complete list of configuration options.

## Architecture

### Data Flow

```
Discovery Phase:
  Sitemap Parsing ──┐
  Google Search ────┼──► Queue ──► Worker Pool ──► Database
  List Crawling ────┤
  Tag Exploration ──┘

API Query Phase:
  Client Request ──► API Key Validation ──► Rate Limit Check ──► Query Database
                                                                        │
    TMDB ID ──► TMDB API ──► IMDB ID ──┐                                │
    TVDB ID ──► TMDB API ──► IMDB ID ──┼──► Query by IMDB ID ◄─────────┘
    Direct IDs ────────────────────────┘
```

### Core Components

1. **API Layer** (`app/main.py`): FastAPI application with middleware for authentication, rate limiting, CORS, and metrics
2. **Data Models** (`app/models.py`): SQLAlchemy models for Item, Queue, User, Lists, Tags, Blacklist
3. **Info Providers** (`app/info_provider/`): Modular integrations with external APIs
4. **Queue Processing** (`app/queue_processor/`): Multi-threaded background task processing
5. **Scheduling** (`app/schedule/`): Automated data discovery and refresh tasks

### Database Schema

- **Item**: Movie/TV data with Douban ID (primary key), IMDB ID, title, year, rating, type
- **Queue**: Background task queue (type, id, params, upsert_time)
- **User**: API key management with rate limiting and admin privileges
- **Schedule**: Scheduled task tracking
- **List**: Douban lists/collections tracking
- **Tag**: Content tags for discovery
- **Blacklist**: Failed item tracking with auto-removal

## Background Tasks

The scheduler runs various automated tasks:

| Task | Description | Default Interval |
|------|-------------|------------------|
| `process_queue` | Process queued items | 1 second |
| `fetch_sitemap` | Discover movies via sitemap | Weekly |
| `discover_lists` | Discover new Douban lists | Varies |
| `discover_tags_by_google` | Find tags via Google | Configurable |
| `refresh` | Refresh existing items | Configurable |
| `backup` | Database backups | Daily |
| `update_db_metrics` | Update Prometheus metrics | 10 minutes |

## Development

### Running Tests

```bash
# Run all tests
./test.sh

# Or with pytest directly
uv run pytest
```

### Code Quality

```bash
# Format and lint code
./scripts/lint.sh

# Check only (CI mode)
./scripts/lint.sh --check
```

### Project Structure

```
douban-idatabase/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration settings
│   ├── models.py               # SQLAlchemy database models
│   ├── database.py             # Database connection & migrations
│   ├── schemas.py              # Pydantic API schemas
│   ├── metrics.py              # Prometheus metrics
│   ├── rate_limit.py           # Rate limiting logic
│   ├── utils.py                # Utility functions
│   ├── http_utils.py           # HTTP request handling
│   ├── redis_utils.py          # Redis caching utilities
│   ├── info_provider/          # External data providers
│   │   ├── detail.py           # Douban detail fetching
│   │   ├── imdb.py             # IMDB ID lookup
│   │   ├── tmdb.py             # TMDB API integration
│   │   ├── sitemap.py          # Sitemap parsing
│   │   ├── lists.py            # Douban list APIs
│   │   ├── tags.py             # Tag processing
│   │   ├── google.py           # Google search
│   │   └── ...
│   ├── queue_processor/        # Background task processing
│   │   ├── worker.py           # Queue worker thread pool
│   │   ├── douban_id_processor.py
│   │   ├── list_processor.py
│   │   └── ...
│   └── schedule/               # Scheduled task system
│       ├── scheduler.py        # Task scheduler
│       ├── task_registry.py    # Task registration
│       └── ...
├── tests/                      # Test suite
├── scripts/                    # Development scripts
├── grafana/                    # Grafana dashboard
├── Dockerfile
├── run.sh
└── pyproject.toml
```

## External API Integration

### Douban
- Mobile API and web scraping
- Cookie-based authentication support
- Rate limiting with fallback strategies (proxy, ZenRows)

### IMDB
- ID lookup via CSV datasets
- Mobile description page parsing
- Desktop HTML fallback (optional)

### TMDB
- API key authentication
- ID translation (TMDB ↔ IMDB)
- 30-day caching for mappings

### TVDB
- ID translation via TMDB API
- 30-day caching for mappings

## Monitoring

Prometheus metrics are exposed at `/metrics` (admin only):

- `api_requests_total`: Total API requests by endpoint, method, status
- `api_request_duration_seconds`: Request duration histogram
- `user_requests_total`: Requests per user
- `rate_limit_hits_total`: Rate limit hits
- `db_stats_*`: Database statistics

A Grafana dashboard template is available in `grafana/dashboard.json`.

## Rate Limiting Strategy

The system implements multi-level rate limiting:

1. **Per-User Limits**: Each API key has configurable rate limits and time windows
2. **Anonymous IP-Based**: For requests without API keys (if enabled)
3. **External API Rate Limiting**: Intelligent retry logic with fallback strategies

When rate limited, the system can fall back to:
- Proxy servers (`REQUESTS_PROXIES`)
- ZenRows proxy service
