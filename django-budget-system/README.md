# Django + Celery Budget Management System

A comprehensive backend system for managing advertising budgets with automatic campaign control based on spend limits and dayparting schedules.

## Features

- **Multi-Brand Support**: Manage multiple brands with individual daily/monthly budgets
- **Campaign Management**: Automatic campaign activation/deactivation based on budget and time constraints
- **Dayparting Control**: Time-based campaign scheduling with timezone support
- **Real-time Budget Tracking**: Immediate spend recording and budget enforcement
- **Automated Resets**: Daily and monthly budget resets with campaign reactivation
- **Admin Interface**: Full Django admin for system management
- **RESTful API**: Endpoints for spend recording and campaign status monitoring

## Tech Stack

- **Django 5.1.2**: Web framework and ORM
- **Celery 5.5.3**: Background task processing
- **Redis**: Message broker and result backend
- **SQLite**: Database (easily switchable to PostgreSQL)
- **Python Type Hints**: Full static typing with mypy

## Project Structure

```
budget_management/
├── budget_management/          # Django project settings
│   ├── __init__.py
│   ├── celery.py              # Celery configuration
│   ├── settings.py            # Django settings
│   └── urls.py                # Main URL configuration
├── budget_system/             # Main application
│   ├── models.py              # Data models
│   ├── admin.py               # Admin interface
│   ├── views.py               # API views
│   ├── urls.py                # App URL configuration
│   ├── tasks.py               # Celery tasks
│   └── migrations/            # Database migrations
├── requirements.txt           # Python dependencies
├── mypy.ini                  # Type checking configuration
└── README.md                 # This file
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- Redis server
- pip or pipenv

### 1. Clone Repository

```bash
git clone <repository-url>
cd budget_management
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Redis

**Windows:**
```bash
redis-server
```

**macOS (with Homebrew):**
```bash
brew services start redis
```

**Linux:**
```bash
sudo systemctl start redis-server
```

### 4. Database Setup

```bash
# Create and apply migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user (optional)
python manage.py createsuperuser
```

### 5. Start Services

**Terminal 1 - Django Development Server:**
```bash
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```bash
celery -A budget_management worker --loglevel=info
```

**Terminal 3 - Celery Beat (Scheduler):**
```bash
celery -A budget_management beat --loglevel=info
```

## Data Models

### Brand
Represents an advertising brand with budget limits and timezone settings.
- `name`: Brand identifier
- `daily_budget`: Maximum daily spend
- `monthly_budget`: Maximum monthly spend  
- `timezone`: Operating timezone for dayparting
- `is_active`: Enable/disable brand

### Campaign
Individual advertising campaigns belonging to brands.
- `brand`: Foreign key to Brand
- `name`: Campaign identifier
- `status`: Current state (ACTIVE, PAUSED_BUDGET, PAUSED_DAYPART, INACTIVE)
- `is_active`: Manual on/off switch

### DaypartingSchedule
Defines when campaigns can run during the week.
- `campaign`: Foreign key to Campaign
- `day_of_week`: Day (0=Monday, 6=Sunday)
- `start_hour` / `end_hour`: Time window (0-23)
- `is_active`: Enable/disable schedule

### SpendRecord
Immutable audit trail of all advertising spend.
- `brand` / `campaign`: Foreign keys
- `amount`: Spend amount
- `spend_date` / `spend_datetime`: When spend occurred

### BudgetSummary
Aggregated daily/monthly spend for performance optimization.
- `brand`: Foreign key
- `date`: Summary date
- `daily_spend` / `monthly_spend`: Accumulated amounts
- `daily_remaining` / `monthly_remaining`: Calculated remaining budgets

## API Endpoints

### Record Spend
```http
POST /api/spend/
Content-Type: application/json

{
  "brand_id": 1,
  "campaign_id": 1,
  "amount": 25.50,
  "spend_datetime": "2024-01-15T10:30:00Z"  // Optional
}
```

### Get Campaign Status
```http
GET /api/campaigns/1/status/
```

**Response:**
```json
{
  "success": true,
  "data": {
    "campaign_id": 1,
    "campaign_name": "Nike Summer Sale",
    "brand_name": "Nike",
    "status": "ACTIVE",
    "can_run_now": true,
    "is_within_dayparting": true,
    "brand_budget_status": {
      "daily_remaining": 750.00,
      "monthly_remaining": 15000.00
    }
  }
}
```

### Toggle Campaign
```http
POST /api/campaigns/1/toggle/
Content-Type: application/json

{
  "action": "activate"  // or "deactivate"
}
```

### Get Brand Status
```http
GET /api/brands/1/status/
```

## System Workflow

### Daily Operations

**12:01 AM (Brand Timezone):**
- Daily budget reset task runs
- Daily spend counters reset to $0
- Campaigns paused for daily budget limits are reactivated

**Every 5 Minutes:**
- Campaign status monitoring
- Automatic pause if budget exceeded
- Reactivation when budget becomes available

**Every Hour:**
- Dayparting enforcement check
- Campaign pause/activation based on time windows

**Real-time:**
- Spend recording via API
- Immediate budget limit checks

### Monthly Operations

**1st Day of Month, 12:01 AM:**
- Monthly budget reset
- Monthly spend counters reset to $0
- Campaigns paused for monthly limits are reactivated

### Background Tasks

1. **`check_campaign_dayparting`**: Enforces time-based campaign scheduling
2. **`update_campaign_status`**: Monitors and updates campaign states based on budget
3. **`reset_daily_budgets`**: Resets daily spend counters and reactivates campaigns
4. **`reset_monthly_budgets`**: Resets monthly spend counters and reactivates campaigns
5. **`record_spend`**: Processes spend transactions and updates budgets

## Admin Interface

Access the Django admin at `http://localhost:8000/admin/` to:
- Manage brands and their budgets
- Create and configure campaigns
- Set up dayparting schedules
- View spend records and budget summaries
- Monitor system health

## Type Checking

Run type checking with mypy:
```bash
mypy .
```

Configuration is in `mypy.ini` with strict settings enabled.

## Development & Testing

### Manual Testing Workflow

1. Create a brand via admin interface
2. Add campaigns with dayparting schedules
3. Record spend via API endpoints
4. Observe automatic campaign pausing when budgets exceeded
5. Verify daily/monthly resets reactivate campaigns

### Monitoring

- Check Celery worker logs for task execution
- Monitor Django logs for API request handling
- Use Redis CLI to inspect task queues: `redis-cli monitor`

## Assumptions & Simplifications

1. **Timezone Handling**: All brands operate in their specified timezone for dayparting, but spend recording uses UTC
2. **Budget Enforcement**: Campaigns are paused immediately when budgets are exceeded (no grace period)
3. **Dayparting Logic**: Campaigns require explicit schedule entries to run (no schedule = no running)
4. **Monthly Calculations**: Monthly budgets reset on the 1st day regardless of when the brand was created
5. **Spend Validation**: Assumes spend amounts are always positive and valid
6. **Concurrency**: Uses Celery's built-in task queuing for spend recording to handle concurrent requests

## Architecture Decisions

- **BudgetSummary Model**: Denormalized data for performance - avoids expensive aggregation queries
- **Separate SpendRecord**: Maintains immutable audit trail while allowing summary optimizations  
- **Status-based Campaign Control**: Explicit status field makes debugging and monitoring easier
- **Timezone per Brand**: Allows global brands to operate in their local time zones
- **Celery for All Background Work**: Consistent async processing for all time-based operations

## Production Considerations

For production deployment:
1. Switch to PostgreSQL database
2. Use Redis cluster for high availability
3. Add proper logging and monitoring
4. Implement API authentication
5. Add rate limiting and input validation
6. Set up proper error alerting
7. Consider database connection pooling
8. Add health check endpoints

## Environment Setup

1. Copy the environment template:
   ```bash
   cp .env.example .env

## License

This project is for demonstration purposes as part of a coding challenge.