# Django + Celery Budget Management System - Pseudo Code Design

## Data Models

### Brand Model
```
Brand:
    - id: Primary Key
    - name: String (e.g., "Nike", "Coca-Cola")
    - daily_budget: Decimal (e.g., 1000.00)
    - monthly_budget: Decimal (e.g., 25000.00)
    - timezone: String (e.g., "America/New_York")
    - is_active: Boolean
    - created_at: DateTime
    - updated_at: DateTime
```

### Campaign Model
```
Campaign:
    - id: Primary Key
    - brand: Foreign Key to Brand
    - name: String (e.g., "Nike Summer Sale")
    - status: Choice Field ["ACTIVE", "PAUSED_BUDGET", "PAUSED_DAYPART", "INACTIVE"]
    - is_active: Boolean (manual on/off switch)
    - created_at: DateTime
    - updated_at: DateTime
```

### DaypartingSchedule Model
```
DaypartingSchedule:
    - id: Primary Key
    - campaign: Foreign Key to Campaign
    - day_of_week: Integer (0=Monday, 6=Sunday)
    - start_hour: Integer (0-23, e.g., 8 for 8 AM)
    - end_hour: Integer (0-23, e.g., 22 for 10 PM)
    - is_active: Boolean
```

### SpendRecord Model
```
SpendRecord:
    - id: Primary Key
    - brand: Foreign Key to Brand
    - campaign: Foreign Key to Campaign
    - amount: Decimal
    - spend_date: Date
    - spend_datetime: DateTime
    - record_type: Choice Field ["DAILY", "MONTHLY"]
    - created_at: DateTime
```

### BudgetSummary Model (Aggregated Data)
```
BudgetSummary:
    - id: Primary Key
    - brand: Foreign Key to Brand
    - date: Date
    - daily_spend: Decimal (sum of today's spending)
    - monthly_spend: Decimal (sum of this month's spending)
    - daily_remaining: Decimal (daily_budget - daily_spend)
    - monthly_remaining: Decimal (monthly_budget - monthly_spend)
    - updated_at: DateTime
```

## Core Business Logic

### 1. Spend Tracking Logic
```
FUNCTION record_spend(campaign_id, amount, timestamp):
    campaign = get_campaign(campaign_id)
    brand = campaign.brand
    spend_date = extract_date(timestamp)
    
    // Create spend record
    spend_record = CREATE SpendRecord(
        brand=brand,
        campaign=campaign,
        amount=amount,
        spend_date=spend_date,
        spend_datetime=timestamp,
        record_type="DAILY"
    )
    
    // Update or create daily summary
    daily_summary = get_or_create_budget_summary(brand, spend_date)
    daily_summary.daily_spend += amount
    daily_summary.daily_remaining = brand.daily_budget - daily_summary.daily_spend
    
    // Update monthly summary
    monthly_summary = get_or_create_monthly_summary(brand, spend_date)
    monthly_summary.monthly_spend += amount
    monthly_summary.monthly_remaining = brand.monthly_budget - monthly_summary.monthly_spend
    
    // Check budget limits
    IF daily_summary.daily_remaining <= 0 OR monthly_summary.monthly_remaining <= 0:
        pause_brand_campaigns_for_budget(brand)
    
    SAVE all records
END FUNCTION
```

### 2. Budget Enforcement Logic
```
FUNCTION pause_brand_campaigns_for_budget(brand):
    campaigns = get_active_campaigns(brand)
    
    FOR EACH campaign IN campaigns:
        IF campaign.status == "ACTIVE":
            campaign.status = "PAUSED_BUDGET"
            SAVE campaign
            LOG "Campaign {campaign.name} paused due to budget exceeded"
END FUNCTION

FUNCTION reactivate_campaigns_for_budget(brand):
    paused_campaigns = get_campaigns_by_status(brand, "PAUSED_BUDGET")
    
    FOR EACH campaign IN paused_campaigns:
        IF brand_has_budget_remaining(brand) AND is_within_dayparting_window(campaign):
            campaign.status = "ACTIVE"
            SAVE campaign
            LOG "Campaign {campaign.name} reactivated - budget available"
END FUNCTION
```

### 3. Dayparting Logic
```
FUNCTION check_dayparting_for_campaign(campaign, current_time):
    brand_timezone = campaign.brand.timezone
    local_time = convert_to_timezone(current_time, brand_timezone)
    current_day = get_day_of_week(local_time)  // 0=Monday, 6=Sunday
    current_hour = get_hour(local_time)        // 0-23
    
    schedules = get_dayparting_schedules(campaign, current_day)
    
    IF schedules is empty:
        RETURN False  // No schedule = not allowed to run
    
    FOR EACH schedule IN schedules:
        IF schedule.start_hour <= current_hour <= schedule.end_hour:
            RETURN True
    
    RETURN False
END FUNCTION

FUNCTION enforce_dayparting_for_campaign(campaign):
    current_time = get_current_time()
    is_allowed = check_dayparting_for_campaign(campaign, current_time)
    
    IF is_allowed AND campaign.status == "PAUSED_DAYPART":
        // Check if budget is also available
        IF brand_has_budget_remaining(campaign.brand):
            campaign.status = "ACTIVE"
            LOG "Campaign {campaign.name} activated - within dayparting window"
    
    ELIF NOT is_allowed AND campaign.status == "ACTIVE":
        campaign.status = "PAUSED_DAYPART"
        LOG "Campaign {campaign.name} paused - outside dayparting window"
    
    SAVE campaign
END FUNCTION
```

### 4. Budget Reset Logic
```
FUNCTION reset_daily_budgets():
    today = get_current_date()
    all_brands = get_all_active_brands()
    
    FOR EACH brand IN all_brands:
        // Reset daily spend to 0
        summary = get_or_create_budget_summary(brand, today)
        summary.daily_spend = 0
        summary.daily_remaining = brand.daily_budget
        SAVE summary
        
        // Reactivate campaigns paused due to daily budget
        reactivate_campaigns_for_budget(brand)
        
        LOG "Daily budget reset for brand {brand.name}"
END FUNCTION

FUNCTION reset_monthly_budgets():
    today = get_current_date()
    first_day_of_month = get_first_day_of_month(today)
    all_brands = get_all_active_brands()
    
    FOR EACH brand IN all_brands:
        // Reset monthly spend to 0
        summary = get_or_create_budget_summary(brand, today)
        summary.monthly_spend = 0
        summary.monthly_remaining = brand.monthly_budget
        SAVE summary
        
        // Reactivate campaigns paused due to monthly budget
        reactivate_campaigns_for_budget(brand)
        
        LOG "Monthly budget reset for brand {brand.name}"
END FUNCTION
```

## Celery Task Definitions

### 1. Daily Reset Task
```
CELERY_TASK daily_budget_reset_task():
    LOG "Starting daily budget reset task"
    
    TRY:
        reset_daily_budgets()
        LOG "Daily budget reset completed successfully"
    CATCH Exception as e:
        LOG_ERROR "Daily budget reset failed: {e}"
        // Send alert to administrators
END TASK

// Schedule: Run every day at 12:01 AM in each brand's timezone
SCHEDULE: cron(minute=1, hour=0)
```

### 2. Monthly Reset Task
```
CELERY_TASK monthly_budget_reset_task():
    LOG "Starting monthly budget reset task"
    
    TRY:
        reset_monthly_budgets()
        LOG "Monthly budget reset completed successfully"
    CATCH Exception as e:
        LOG_ERROR "Monthly budget reset failed: {e}"
        // Send alert to administrators
END TASK

// Schedule: Run on the 1st day of every month at 12:01 AM
SCHEDULE: cron(minute=1, hour=0, day_of_month=1)
```

### 3. Dayparting Enforcement Task
```
CELERY_TASK dayparting_enforcement_task():
    LOG "Starting dayparting enforcement check"
    
    all_campaigns = get_all_campaigns_with_dayparting()
    
    FOR EACH campaign IN all_campaigns:
        TRY:
            enforce_dayparting_for_campaign(campaign)
        CATCH Exception as e:
            LOG_ERROR "Dayparting enforcement failed for campaign {campaign.id}: {e}"
    
    LOG "Dayparting enforcement check completed"
END TASK

// Schedule: Run every 5 minutes
SCHEDULE: cron(minute='*/5')
```

### 4. Budget Monitoring Task
```
CELERY_TASK budget_monitoring_task():
    LOG "Starting budget monitoring check"
    
    all_brands = get_all_active_brands()
    
    FOR EACH brand IN all_brands:
        TRY:
            daily_summary = get_budget_summary(brand, today())
            
            // Check if any campaigns should be paused
            IF daily_summary.daily_remaining <= 0 OR daily_summary.monthly_remaining <= 0:
                pause_brand_campaigns_for_budget(brand)
            
            // Check if any campaigns can be reactivated
            ELIF daily_summary.daily_remaining > 0 AND daily_summary.monthly_remaining > 0:
                reactivate_campaigns_for_budget(brand)
                
        CATCH Exception as e:
            LOG_ERROR "Budget monitoring failed for brand {brand.id}: {e}"
    
    LOG "Budget monitoring check completed"
END TASK

// Schedule: Run every 10 minutes
SCHEDULE: cron(minute='*/10')
```

## Key Helper Functions

### Utility Functions
```
FUNCTION brand_has_budget_remaining(brand):
    today = get_current_date()
    summary = get_budget_summary(brand, today)
    
    RETURN summary.daily_remaining > 0 AND summary.monthly_remaining > 0
END FUNCTION

FUNCTION get_campaigns_eligible_for_activation(brand):
    paused_campaigns = get_campaigns_by_status(brand, ["PAUSED_BUDGET", "PAUSED_DAYPART"])
    eligible_campaigns = []
    
    FOR EACH campaign IN paused_campaigns:
        IF brand_has_budget_remaining(brand) AND is_within_dayparting_window(campaign):
            eligible_campaigns.append(campaign)
    
    RETURN eligible_campaigns
END FUNCTION

FUNCTION calculate_spend_velocity(brand, hours=1):
    // Calculate spend rate per hour for predictive budget management
    current_time = get_current_time()
    start_time = current_time - hours
    
    recent_spend = sum_spend_records(brand, start_time, current_time)
    RETURN recent_spend / hours
END FUNCTION
```

## API Endpoints (Django Views)

### Spend Recording Endpoint
```
API_ENDPOINT record_campaign_spend(request):
    campaign_id = request.POST.get('campaign_id')
    amount = request.POST.get('amount')
    timestamp = request.POST.get('timestamp', current_time())
    
    VALIDATE input_data
    
    TRY:
        record_spend(campaign_id, amount, timestamp)
        RETURN success_response()
    CATCH Exception as e:
        RETURN error_response(e)
END ENDPOINT
```

### Campaign Status Endpoint
```
API_ENDPOINT get_campaign_status(request, campaign_id):
    campaign = get_campaign(campaign_id)
    budget_summary = get_budget_summary(campaign.brand, today())
    
    response_data = {
        'campaign_id': campaign.id,
        'status': campaign.status,
        'is_within_dayparting': is_within_dayparting_window(campaign),
        'brand_daily_remaining': budget_summary.daily_remaining,
        'brand_monthly_remaining': budget_summary.monthly_remaining
    }
    
    RETURN json_response(response_data)
END ENDPOINT
```

## System Workflow Summary

### Daily Workflow:
1. **12:01 AM**: Daily budget reset task runs
   - Reset daily spend to 0 for all brands
   - Reactivate campaigns paused due to daily budget limits

2. **Every 5 minutes**: Dayparting enforcement
   - Check if campaigns should be paused/activated based on time windows

3. **Every 10 minutes**: Budget monitoring
   - Check current spend against budgets
   - Pause campaigns if limits exceeded
   - Reactivate campaigns if budget becomes available

4. **Throughout day**: Spend recording
   - Real-time spend tracking via API calls
   - Immediate budget limit enforcement

### Monthly Workflow:
1. **1st day of month, 12:01 AM**: Monthly budget reset
   - Reset monthly spend to 0 for all brands
   - Reactivate campaigns paused due to monthly budget limits

## Error Handling & Logging

### Critical Operations:
- All budget operations wrapped in database transactions
- Comprehensive logging for audit trails
- Alerting system for task failures
- Retry mechanisms for transient failures
- Dead letter queues for failed tasks

### Monitoring Points:
- Budget utilization rates
- Campaign activation/deactivation events
- Task execution success/failure rates
- API endpoint response times
- Database query performance