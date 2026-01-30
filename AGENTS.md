# AGENTS.md

This file provides guidance for AI coding agents working with this repository.

## Project Overview

Douban iDatabase is a FastAPI-based web API service that aggregates movie/TV metadata from multiple sources (Douban, IMDB, TMDB, TVDB). It features comprehensive data collection, caching, background processing, and API management with rate limiting and monitoring.

## Development Commands

```bash
# Setup and initialization
./scripts/init_repo.sh          # Initialize repository and setup environment
uv sync                         # Install dependencies with UV package manager

# Code quality and testing
./scripts/lint.sh               # Run ruff formatting and linting
./test.sh                       # Run pytest test suite
ruff check                      # Lint only
ruff format                     # Format only

# Running the application
./run.sh                        # Start FastAPI development server
python -m app.main              # Alternative way to start server

# Background processing
python -m app.queue_processor   # Run queue processor for background tasks
```

## Architecture Overview

### Core Components

1. **API Layer** (`app/main.py`): FastAPI application with middleware for authentication, rate limiting, CORS, and metrics
2. **Data Models** (`app/models.py`): SQLAlchemy models for Item, Queue, User, Lists, Tags
3. **Info Providers** (`app/info_provider/`): Modular integrations with external APIs (Douban, IMDB, TMDB, etc.)
4. **Queue Processing** (`app/queue_processor/`): Multi-threaded background task processing system
5. **Scheduling** (`app/schedule/`): Automated data discovery and refresh tasks

### Data Flow

- **Discovery**: Sitemap parsing, list discovery, tag exploration, Google search
- **Processing**: Queue-based background processing with configurable workers
- **Storage**: SQLite database with SQLAlchemy ORM and Redis caching
- **API**: REST endpoints with multi-ID lookup and external ID conversion

## Key Design Patterns

### Multi-Source Data Aggregation
Information providers follow a common interface in `app/info_provider/base.py`. Each provider implements specific logic for their data source while maintaining consistent data models.

### Queue-Based Background Processing
Tasks are queued in the database and processed by background workers. Queue processor handles different task types (item fetch, list processing, sitemap crawling) with rate limiting and error handling.

### Configuration Management
Environment-based configuration through `.env` files with comprehensive settings for all system aspects. See `.env.sample` for available options.

### Rate Limiting Strategy
Multi-level rate limiting: per-user API key limits, anonymous IP-based limits, and external API rate limiting with intelligent retry logic.

## Database

- **Primary**: SQLite with SQLAlchemy ORM
- **Migrations**: Located in `app/migrations/`
- **Models**: All models defined in `app/models.py`
- **Relationships**: Items linked to external IDs, tags, and processing queues

## Testing

- **Framework**: pytest with comprehensive fixtures
- **Structure**: Tests mirror the app structure in `tests/` directory
- **Key test files**: 
  - `tests/test_main.py`: API endpoint tests
  - `tests/test_info_provider/`: Provider-specific tests
  - `tests/test_queue_processor/`: Background processing tests

## External API Integration

Each info provider handles its own API specifics:
- **Douban**: Mobile API and web scraping with cookie management
- **IMDB**: ID lookup and basic metadata
- **TMDB**: Comprehensive movie database with API key authentication
- **TVDB**: TV series specific data

## Important Files

- `app/config/settings.py`: Centralized configuration management
- `app/database.py`: Database connection and session management
- `app/schemas.py`: Pydantic models for API request/response validation
- `docker-compose.yml`: Development environment with Redis
- `.env.sample`: Template for environment configuration

## Background Tasks

The queue processor handles various task types defined in `app/queue_processor/task_type.py`:
- Item fetching and updating
- List processing for bulk operations
- Sitemap crawling for systematic discovery
- Tag exploration for content categorization
