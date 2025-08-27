from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from typing import Optional, List
from datetime import date, datetime
import pytz


class Brand(models.Model):
    """
    Represents an advertising brand with daily and monthly budget limits.
    Each brand can have multiple campaigns and operates in a specific timezone.
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Brand name (e.g., 'Nike', 'Coca-Cola')"
    )
    
    daily_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Daily budget limit in dollars"
    )
    
    monthly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monthly budget limit in dollars"
    )
    
    # Timezone 
    TIMEZONE_CHOICES = [
    # Pakistan and nearby countries
    ('Asia/Karachi', 'Pakistan Standard Time'),
    ('Asia/Kolkata', 'India Standard Time'),
    ('Asia/Dhaka', 'Bangladesh Standard Time'),
    ('Asia/Kabul', 'Afghanistan Time'),
    ('Asia/Tehran', 'Iran Standard Time'),
    ('Asia/Dubai', 'UAE Standard Time'),
    ('Asia/Riyadh', 'Saudi Arabia Standard Time'),
    
    # China and East Asia
    ('Asia/Shanghai', 'China Standard Time'),
    ('Asia/Hong_Kong', 'Hong Kong Time'),
    ('Asia/Tokyo', 'Japan Standard Time'),
    ('Asia/Seoul', 'South Korea Standard Time'),
    ('Asia/Singapore', 'Singapore Standard Time'),
    ('Asia/Bangkok', 'Thailand Standard Time'),
    ('Asia/Jakarta', 'Indonesia Western Time'),
    ('Asia/Manila', 'Philippines Standard Time'),
    
    # Europe
    ('Europe/London', 'United Kingdom Time'),
    ('Europe/Paris', 'Central European Time'),
    ('Europe/Berlin', 'Germany Time'),
    ('Europe/Rome', 'Italy Time'),
    ('Europe/Madrid', 'Spain Time'),
    ('Europe/Amsterdam', 'Netherlands Time'),
    ('Europe/Stockholm', 'Sweden Time'),
    ('Europe/Moscow', 'Moscow Standard Time'),
    ('Europe/Istanbul', 'Turkey Time'),
    
    # North America
    ('America/New_York', 'Eastern Time (US)'),
    ('America/Chicago', 'Central Time (US)'),
    ('America/Denver', 'Mountain Time (US)'),
    ('America/Los_Angeles', 'Pacific Time (US)'),
    ('America/Toronto', 'Eastern Time (Canada)'),
    ('America/Vancouver', 'Pacific Time (Canada)'),
    
    # Australia and Oceania
    ('Australia/Sydney', 'Australian Eastern Time'),
    ('Australia/Melbourne', 'Australian Eastern Time'),
    ('Australia/Perth', 'Australian Western Time'),
    ('Pacific/Auckland', 'New Zealand Standard Time'),
    
    # Africa and Middle East
    ('Africa/Cairo', 'Egypt Standard Time'),
    ('Africa/Johannesburg', 'South Africa Standard Time'),
    ('Africa/Lagos', 'West Africa Time'),
    ('Africa/Nairobi', 'East Africa Time'),
    
    # South America
    ('America/Sao_Paulo', 'Brazil Time'),
    ('America/Argentina/Buenos_Aires', 'Argentina Time'),
    ('America/Lima', 'Peru Time'),
    
    # Others
    ('UTC', 'Coordinated Universal Time'),
]
    
    timezone = models.CharField(
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='UTC',
        help_text="Brand's operating timezone for dayparting calculations"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this brand is actively being managed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'brand'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['timezone']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} (Daily: ${self.daily_budget}, Monthly: ${self.monthly_budget})"
    
    def get_local_time(self, utc_time: Optional[datetime] = None) -> datetime:
        """Convert UTC time to brand's local timezone"""
        if utc_time is None:
            utc_time = timezone.now()
        
        brand_tz = pytz.timezone(self.timezone)
        return utc_time.astimezone(brand_tz)
    
    def has_budget_remaining(self, check_date: Optional[date] = None) -> bool:
        """Check if brand has both daily and monthly budget remaining"""
        if check_date is None:
            check_date = timezone.now().date()
        
        try:
            summary = BudgetSummary.objects.get(brand=self, date=check_date)
            return (summary.daily_remaining > 0 and summary.monthly_remaining > 0)
        except BudgetSummary.DoesNotExist:
            return True  # No spending recorded yet


class Campaign(models.Model):
    """
    Represents an advertising campaign belonging to a brand.
    Campaigns can be in various states based on budget limits and dayparting rules.
    """
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active - Currently running'),
        ('PAUSED_BUDGET', 'Paused - Budget exceeded'),
        ('PAUSED_DAYPART', 'Paused - Outside dayparting window'),
        ('INACTIVE', 'Inactive - Manually disabled'),
    ]
    
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='campaigns',
        help_text="The brand this campaign belongs to"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Campaign name (e.g., 'Nike Summer Sale')"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='INACTIVE',
        help_text="Current campaign status"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Manual on/off switch for the campaign"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaign'
        ordering = ['brand__name', 'name']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['is_active']),
        ]
        unique_together = ['brand', 'name']
    
    def __str__(self) -> str:
        return f"{self.brand.name} - {self.name} ({self.status})"
    
    def can_run_now(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if campaign can run right now based on:
        1. Manual activation (is_active)
        2. Budget availability
        3. Dayparting schedule
        """
        if not self.is_active:
            return False
        
        if not self.brand.has_budget_remaining():
            return False
        
        return self.is_within_dayparting_window(check_time)
    
    def is_within_dayparting_window(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is within any dayparting schedule"""
        if check_time is None:
            check_time = timezone.now()
        
        local_time = self.brand.get_local_time(check_time)
        current_day = local_time.weekday()  # 0=Monday, 6=Sunday
        current_hour = local_time.hour
        
        schedules = self.dayparting_schedules.filter(
            day_of_week=current_day,
            is_active=True
        )
        
        if not schedules.exists():
            return False  # No schedule = not allowed to run
        
        for schedule in schedules:
            if schedule.start_hour <= current_hour <= schedule.end_hour:
                return True
        
        return False
    
    def pause_for_budget(self) -> None:
        """Pause campaign due to budget exceeded"""
        self.status = 'PAUSED_BUDGET'
        self.save(update_fields=['status', 'updated_at'])
    
    def pause_for_dayparting(self) -> None:
        """Pause campaign due to outside dayparting window"""
        self.status = 'PAUSED_DAYPART'
        self.save(update_fields=['status', 'updated_at'])
    
    def activate(self) -> None:
        """Activate campaign if conditions are met"""
        if self.can_run_now():
            self.status = 'ACTIVE'
            self.save(update_fields=['status', 'updated_at'])


class DaypartingSchedule(models.Model):
    """
    Defines when a campaign is allowed to run during the week.
    Each campaign can have multiple schedules for different days/times.
    """
    
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='dayparting_schedules',
        help_text="Campaign this schedule applies to"
    )
    
    day_of_week = models.IntegerField(
        choices=DAY_CHOICES,
        help_text="Day of the week (0=Monday, 6=Sunday)"
    )
    
    start_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Starting hour (0-23, e.g., 8 for 8 AM)"
    )
    
    end_hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text="Ending hour (0-23, e.g., 22 for 10 PM)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schedule is currently active"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dayparting_schedule'
        ordering = ['campaign', 'day_of_week', 'start_hour']
        indexes = [
            models.Index(fields=['campaign', 'day_of_week']),
            models.Index(fields=['is_active']),
        ]
    
    def clean(self) -> None:
        """Validate that start_hour <= end_hour"""
        if self.start_hour > self.end_hour:
            raise ValueError("Start hour must be less than or equal to end hour")
    
    def __str__(self) -> str:
        day_name = dict(self.DAY_CHOICES)[self.day_of_week]
        return f"{self.campaign.name} - {day_name} {self.start_hour:02d}:00-{self.end_hour:02d}:00"


class SpendRecord(models.Model):
    """
    Immutable record of advertising spend.
    Each record represents a single spend transaction for audit trail.
    """
    
    RECORD_TYPE_CHOICES = [
        ('DAILY', 'Daily spend record'),
        ('MONTHLY', 'Monthly spend record'),
    ]
    
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='spend_records',
        help_text="Brand that incurred this spend"
    )
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='spend_records',
        help_text="Campaign that generated this spend"
    )
    
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Spend amount in dollars"
    )
    
    spend_date = models.DateField(
        help_text="Date when the spend occurred"
    )
    
    spend_datetime = models.DateTimeField(
        help_text="Exact timestamp when spend was recorded"
    )
    
    record_type = models.CharField(
        max_length=10,
        choices=RECORD_TYPE_CHOICES,
        default='DAILY',
        help_text="Type of spend record"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'spend_record'
        ordering = ['-spend_datetime']
        indexes = [
            models.Index(fields=['brand', 'spend_date']),
            models.Index(fields=['campaign', 'spend_date']),
            models.Index(fields=['spend_date']),
            models.Index(fields=['-spend_datetime']),
        ]
    
    def __str__(self) -> str:
        return f"{self.brand.name} - {self.campaign.name}: ${self.amount} on {self.spend_date}"
    
    def save(self, *args, **kwargs) -> None:
        """Auto-set spend_date from spend_datetime if not provided"""
        if not self.spend_date and self.spend_datetime:
            self.spend_date = self.spend_datetime.date()
        super().save(*args, **kwargs)


class BudgetSummary(models.Model):
    """
    Aggregated daily and monthly spend summary for fast budget checks.
    This model is updated frequently to avoid expensive queries on SpendRecord.
    """
    
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='budget_summaries',
        help_text="Brand this summary belongs to"
    )
    
    date = models.DateField(
        help_text="Date this summary applies to"
    )
    
    daily_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total spend for this day"
    )
    
    monthly_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total spend for this month up to this date"
    )
    
    daily_remaining = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Remaining daily budget (calculated field)"
    )
    
    monthly_remaining = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Remaining monthly budget (calculated field)"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'budget_summary'
        ordering = ['-date']
        unique_together = ['brand', 'date']
        indexes = [
            models.Index(fields=['brand', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['brand', '-date']),
        ]
    
    def __str__(self) -> str:
        return f"{self.brand.name} - {self.date}: Daily ${self.daily_spend}/${self.brand.daily_budget}"
    
    def save(self, *args, **kwargs) -> None:
        """Auto-calculate remaining budgets"""
        self.daily_remaining = self.brand.daily_budget - self.daily_spend
        self.monthly_remaining = self.brand.monthly_budget - self.monthly_spend
        super().save(*args, **kwargs)
    
    def update_daily_spend(self, amount: Decimal) -> None:
        """Add to daily spend and recalculate remaining budgets"""
        self.daily_spend += amount
        self.save(update_fields=['daily_spend', 'daily_remaining', 'updated_at'])
    
    def update_monthly_spend(self, amount: Decimal) -> None:
        """Add to monthly spend and recalculate remaining budgets"""
        self.monthly_spend += amount
        self.save(update_fields=['monthly_spend', 'monthly_remaining', 'updated_at'])
    
    def reset_daily_spend(self) -> None:
        """Reset daily spend to 0 (used for daily resets)"""
        self.daily_spend = Decimal('0.00')
        self.save(update_fields=['daily_spend', 'daily_remaining', 'updated_at'])
    
    def reset_monthly_spend(self) -> None:
        """Reset monthly spend to 0 (used for monthly resets)"""
        self.monthly_spend = Decimal('0.00')
        self.save(update_fields=['monthly_spend', 'monthly_remaining', 'updated_at'])
    
    @classmethod
    def get_or_create_for_date(cls, brand: Brand, target_date: date) -> 'BudgetSummary':
        """Get or create budget summary for a specific date"""
        summary, created = cls.objects.get_or_create(
            brand=brand,
            date=target_date,
            defaults={
                'daily_spend': Decimal('0.00'),
                'monthly_spend': cls._calculate_monthly_spend(brand, target_date),
                'daily_remaining': brand.daily_budget,
                'monthly_remaining': brand.monthly_budget,
            }
        )
        return summary
    
    @classmethod
    def _calculate_monthly_spend(cls, brand: Brand, target_date: date) -> Decimal:
        """Calculate total monthly spend up to target date"""
        first_day = target_date.replace(day=1)
        
        monthly_spend = SpendRecord.objects.filter(
            brand=brand,
            spend_date__gte=first_day,
            spend_date__lte=target_date
        ).aggregate(
            total=models.Sum('amount')
        )['total']
        
        return monthly_spend or Decimal('0.00')