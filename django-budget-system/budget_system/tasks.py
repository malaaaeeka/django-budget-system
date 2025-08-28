from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from typing import List, Dict, Any
from datetime import date, datetime
import logging

from .models import Brand, Campaign, BudgetSummary, SpendRecord

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def check_campaign_dayparting(self) -> None:
    """
    Check all active campaigns and update their status based on dayparting schedules.
    Runs every hour to ensure campaigns are paused/activated according to their schedules.
    """
    try:
        campaigns = Campaign.objects.filter(is_active=True).select_related('brand')
        updated_count = 0
        
        for campaign in campaigns:
            current_time = timezone.now()
            
            if campaign.is_within_dayparting_window(current_time):
                # Campaign should be running - activate if not already active
                if campaign.status == 'PAUSED_DAYPART' and campaign.brand.has_budget_remaining():
                    campaign.activate()
                    updated_count += 1
                    logger.info(f"Activated campaign {campaign.name} - within dayparting window")
            else:
                # Campaign should not be running - pause for dayparting
                if campaign.status == 'ACTIVE':
                    campaign.pause_for_dayparting()
                    updated_count += 1
                    logger.info(f"Paused campaign {campaign.name} - outside dayparting window")
        
        logger.info(f"Dayparting check completed. Updated {updated_count} campaigns.")
        
    except Exception as exc:
        logger.error(f"Error in dayparting check: {str(exc)}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def update_campaign_status(self) -> None:
    """
    Update campaign status based on budget availability.
    Runs every 5 minutes to ensure campaigns are paused when budgets are exceeded.
    """
    try:
        campaigns = Campaign.objects.filter(
            is_active=True,
            status__in=['ACTIVE', 'PAUSED_BUDGET']
        ).select_related('brand')
        
        updated_count = 0
        
        for campaign in campaigns:
            has_budget = campaign.brand.has_budget_remaining()
            
            if not has_budget and campaign.status == 'ACTIVE':
                # Pause campaign due to budget exceeded
                campaign.pause_for_budget()
                updated_count += 1
                logger.info(f"Paused campaign {campaign.name} - budget exceeded")
                
            elif has_budget and campaign.status == 'PAUSED_BUDGET':
                # Reactivate campaign if within dayparting window
                if campaign.is_within_dayparting_window():
                    campaign.activate()
                    updated_count += 1
                    logger.info(f"Reactivated campaign {campaign.name} - budget available")
        
        logger.info(f"Campaign status update completed. Updated {updated_count} campaigns.")
        
    except Exception as exc:
        logger.error(f"Error in campaign status update: {str(exc)}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def reset_daily_budgets(self) -> None:
    """
    Reset daily budgets for all brands at the start of each day.
    Reactivates eligible campaigns that were paused due to daily budget limits.
    """
    try:
        today = timezone.now().date()
        brands = Brand.objects.filter(is_active=True)
        
        reset_count = 0
        reactivated_campaigns = 0
        
        for brand in brands:
            # Get or create budget summary for today
            summary = BudgetSummary.get_or_create_for_date(brand, today)
            
            # Reset daily spend if it's not already 0
            if summary.daily_spend > Decimal('0.00'):
                summary.reset_daily_spend()
                reset_count += 1
                logger.info(f"Reset daily budget for brand {brand.name}")
                
                # Reactivate campaigns that were paused due to daily budget
                paused_campaigns = brand.campaigns.filter(
                    is_active=True,
                    status='PAUSED_BUDGET'
                )
                
                for campaign in paused_campaigns:
                    if campaign.can_run_now():
                        campaign.activate()
                        reactivated_campaigns += 1
                        logger.info(f"Reactivated campaign {campaign.name} after daily budget reset")
        
        logger.info(f"Daily budget reset completed. Reset {reset_count} brands, "
                   f"reactivated {reactivated_campaigns} campaigns.")
        
    except Exception as exc:
        logger.error(f"Error in daily budget reset: {str(exc)}")
        raise self.retry(exc=exc, countdown=300, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def reset_monthly_budgets(self) -> None:
    """
    Reset monthly budgets for all brands at the start of each month.
    Reactivates eligible campaigns that were paused due to monthly budget limits.
    """
    try:
        today = timezone.now().date()
        brands = Brand.objects.filter(is_active=True)
        
        reset_count = 0
        reactivated_campaigns = 0
        
        for brand in brands:
            # Get or create budget summary for today (first day of new month)
            summary = BudgetSummary.get_or_create_for_date(brand, today)
            
            # Reset monthly spend
            if summary.monthly_spend > Decimal('0.00'):
                summary.reset_monthly_spend()
                reset_count += 1
                logger.info(f"Reset monthly budget for brand {brand.name}")
                
                # Reactivate campaigns that were paused due to monthly budget
                paused_campaigns = brand.campaigns.filter(
                    is_active=True,
                    status='PAUSED_BUDGET'
                )
                
                for campaign in paused_campaigns:
                    if campaign.can_run_now():
                        campaign.activate()
                        reactivated_campaigns += 1
                        logger.info(f"Reactivated campaign {campaign.name} after monthly budget reset")
        
        logger.info(f"Monthly budget reset completed. Reset {reset_count} brands, "
                   f"reactivated {reactivated_campaigns} campaigns.")
        
    except Exception as exc:
        logger.error(f"Error in monthly budget reset: {str(exc)}")
        raise self.retry(exc=exc, countdown=300, max_retries=3)


@shared_task(bind=True)
def record_spend(brand_id: int, campaign_id: int, amount: float, spend_datetime: str = None) -> Dict[str, Any]:
    """
    Record a spend transaction and update budget summaries.
    This task would typically be called when ad spend occurs.
    
    Args:
        brand_id: ID of the brand
        campaign_id: ID of the campaign
        amount: Spend amount in dollars
        spend_datetime: ISO format datetime string, defaults to now
    
    Returns:
        Dictionary with operation results
    """
    try:
        from django.core.exceptions import ObjectDoesNotExist
        
        # Parse datetime
        if spend_datetime:
            spend_dt = datetime.fromisoformat(spend_datetime.replace('Z', '+00:00'))
        else:
            spend_dt = timezone.now()
        
        spend_date = spend_dt.date()
        amount_decimal = Decimal(str(amount))
        
        # Get brand and campaign
        try:
            brand = Brand.objects.get(id=brand_id, is_active=True)
            campaign = Campaign.objects.get(id=campaign_id, brand=brand, is_active=True)
        except ObjectDoesNotExist as e:
            logger.error(f"Invalid brand_id {brand_id} or campaign_id {campaign_id}: {str(e)}")
            return {"success": False, "error": "Invalid brand or campaign ID"}
        
        # Create spend record
        spend_record = SpendRecord.objects.create(
            brand=brand,
            campaign=campaign,
            amount=amount_decimal,
            spend_date=spend_date,
            spend_datetime=spend_dt,
            record_type='DAILY'
        )
        
        # Update budget summary
        summary = BudgetSummary.get_or_create_for_date(brand, spend_date)
        summary.update_daily_spend(amount_decimal)
        summary.update_monthly_spend(amount_decimal)
        
        # Check if budget limits exceeded and pause campaign if necessary
        if summary.daily_remaining <= 0 or summary.monthly_remaining <= 0:
            if campaign.status == 'ACTIVE':
                campaign.pause_for_budget()
                logger.info(f"Paused campaign {campaign.name} due to budget exceeded")
        
        logger.info(f"Recorded spend of ${amount_decimal} for campaign {campaign.name}")
        
        return {
            "success": True,
            "spend_record_id": spend_record.id,
            "daily_remaining": float(summary.daily_remaining),
            "monthly_remaining": float(summary.monthly_remaining),
            "campaign_paused": campaign.status != 'ACTIVE'
        }
        
    except Exception as exc:
        logger.error(f"Error recording spend: {str(exc)}")
        raise self.retry(exc=exc, countdown=30, max_retries=5)


@shared_task(bind=True, ignore_result=True)
def cleanup_old_spend_records(self, days_to_keep: int = 90) -> None:
    """
    Clean up old spend records to prevent database bloat.
    Keeps records for specified number of days (default 90).
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now().date() - timedelta(days=days_to_keep)
        
        deleted_count, _ = SpendRecord.objects.filter(
            spend_date__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old spend records older than {cutoff_date}")
        
    except Exception as exc:
        logger.error(f"Error in cleanup task: {str(exc)}")
        raise self.retry(exc=exc, countdown=300, max_retries=2)
        