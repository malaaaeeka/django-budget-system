from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Dict, Any

from .models import Brand, Campaign, BudgetSummary
from .tasks import record_spend


@method_decorator(csrf_exempt, name='dispatch')
class RecordSpendView(View):
    """API endpoint to record advertising spend for a campaign"""
    
    def post(self, request) -> JsonResponse:
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['brand_id', 'campaign_id', 'amount']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            brand_id = int(data['brand_id'])
            campaign_id = int(data['campaign_id'])
            amount = float(data['amount'])
            spend_datetime = data.get('spend_datetime')  # Optional
            
            if amount <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Amount must be greater than 0'
                }, status=400)
            
            # Queue the spend recording task
            if spend_datetime:
                task_result = record_spend.delay(brand_id, campaign_id, amount, spend_datetime)
            else:
                task_result = record_spend.delay(brand_id, campaign_id, amount)
            
            return JsonResponse({
                'success': True,
                'message': 'Spend recording queued',
                'task_id': task_result.id
            })
            
        except (ValueError, InvalidOperation, json.JSONDecodeError) as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid input: {str(e)}'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Internal error: {str(e)}'
            }, status=500)


class CampaignStatusView(View):
    """API endpoint to get campaign status and budget information"""
    
    def get(self, request, campaign_id: int) -> JsonResponse:
        try:
            campaign = Campaign.objects.select_related('brand').get(
                id=campaign_id,
                is_active=True
            )
            
            # Get current budget summary
            today = timezone.now().date()
            try:
                budget_summary = BudgetSummary.objects.get(
                    brand=campaign.brand,
                    date=today
                )
            except BudgetSummary.DoesNotExist:
                budget_summary = BudgetSummary.get_or_create_for_date(
                    campaign.brand, today
                )
            
            # Check if campaign can run now
            can_run = campaign.can_run_now()
            is_within_dayparting = campaign.is_within_dayparting_window()
            has_budget = campaign.brand.has_budget_remaining()
            
            return JsonResponse({
                'success': True,
                'data': {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'brand_name': campaign.brand.name,
                    'status': campaign.status,
                    'is_active': campaign.is_active,
                    'can_run_now': can_run,
                    'is_within_dayparting': is_within_dayparting,
                    'brand_budget_status': {
                        'has_budget_remaining': has_budget,
                        'daily_spent': float(budget_summary.daily_spend),
                        'daily_budget': float(campaign.brand.daily_budget),
                        'daily_remaining': float(budget_summary.daily_remaining),
                        'monthly_spent': float(budget_summary.monthly_spend),
                        'monthly_budget': float(campaign.brand.monthly_budget),
                        'monthly_remaining': float(budget_summary.monthly_remaining),
                    },
                    'dayparting_schedules': [
                        {
                            'day_of_week': schedule.day_of_week,
                            'day_name': dict(schedule.DAY_CHOICES)[schedule.day_of_week],
                            'start_hour': schedule.start_hour,
                            'end_hour': schedule.end_hour,
                            'is_active': schedule.is_active
                        }
                        for schedule in campaign.dayparting_schedules.filter(is_active=True)
                    ]
                }
            })
            
        except ObjectDoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Campaign not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Internal error: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class CampaignToggleView(View):
    """API endpoint to manually activate/deactivate campaigns"""
    
    def post(self, request, campaign_id: int) -> JsonResponse:
        try:
            data = json.loads(request.body)
            action = data.get('action')  # 'activate' or 'deactivate'
            
            if action not in ['activate', 'deactivate']:
                return JsonResponse({
                    'success': False,
                    'error': 'Action must be "activate" or "deactivate"'
                }, status=400)
            
            campaign = Campaign.objects.select_related('brand').get(
                id=campaign_id,
                is_active=True
            )
            
            if action == 'activate':
                if campaign.can_run_now():
                    campaign.activate()
                    message = f'Campaign {campaign.name} activated'
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Campaign cannot be activated - check budget and dayparting'
                    }, status=400)
            
            else:  # deactivate
                campaign.status = 'INACTIVE'
                campaign.save(update_fields=['status', 'updated_at'])
                message = f'Campaign {campaign.name} deactivated'
            
            return JsonResponse({
                'success': True,
                'message': message,
                'new_status': campaign.status
            })
            
        except ObjectDoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Campaign not found'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Internal error: {str(e)}'
            }, status=500)


class BrandStatusView(View):
    """API endpoint to get brand budget status"""
    
    def get(self, request, brand_id: int) -> JsonResponse:
        try:
            brand = Brand.objects.get(id=brand_id, is_active=True)
            
            today = timezone.now().date()
            try:
                budget_summary = BudgetSummary.objects.get(
                    brand=brand,
                    date=today
                )
            except BudgetSummary.DoesNotExist:
                budget_summary = BudgetSummary.get_or_create_for_date(brand, today)
            
            # Get campaign counts by status
            campaign_counts = {
                'total': brand.campaigns.filter(is_active=True).count(),
                'active': brand.campaigns.filter(is_active=True, status='ACTIVE').count(),
                'paused_budget': brand.campaigns.filter(is_active=True, status='PAUSED_BUDGET').count(),
                'paused_daypart': brand.campaigns.filter(is_active=True, status='PAUSED_DAYPART').count(),
                'inactive': brand.campaigns.filter(is_active=True, status='INACTIVE').count(),
            }
            
            return JsonResponse({
                'success': True,
                'data': {
                    'brand_id': brand.id,
                    'brand_name': brand.name,
                    'timezone': brand.timezone,
                    'budget_status': {
                        'daily_spent': float(budget_summary.daily_spend),
                        'daily_budget': float(brand.daily_budget),
                        'daily_remaining': float(budget_summary.daily_remaining),
                        'daily_utilization_percent': round(
                            (float(budget_summary.daily_spend) / float(brand.daily_budget)) * 100, 2
                        ),
                        'monthly_spent': float(budget_summary.monthly_spend),
                        'monthly_budget': float(brand.monthly_budget),
                        'monthly_remaining': float(budget_summary.monthly_remaining),
                        'monthly_utilization_percent': round(
                            (float(budget_summary.monthly_spend) / float(brand.monthly_budget)) * 100, 2
                        ),
                        'has_budget_remaining': brand.has_budget_remaining(),
                    },
                    'campaign_counts': campaign_counts,
                    'local_time': brand.get_local_time().isoformat(),
                }
            })
            
        except ObjectDoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Brand not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Internal error: {str(e)}'
            }, status=500)