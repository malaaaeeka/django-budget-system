# budget_system/management/commands/record_spend.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal
from typing import Any

from budget_system.models import Brand, Campaign
from budget_system.tasks import record_spend


class Command(BaseCommand):
    help = 'Record advertising spend for a campaign'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            'brand_name',
            type=str,
            help='Name of the brand'
        )
        parser.add_argument(
            'campaign_name',
            type=str,
            help='Name of the campaign'
        )
        parser.add_argument(
            'amount',
            type=float,
            help='Spend amount in dollars'
        )
        parser.add_argument(
            '--datetime',
            type=str,
            help='Spend datetime in ISO format (defaults to now)',
            default=None
        )

    def handle(self, *args: Any, **options: Any) -> None:
        brand_name = options['brand_name']
        campaign_name = options['campaign_name']
        amount = options['amount']
        spend_datetime = options['datetime']

        try:
            # Validate amount
            if amount <= 0:
                raise CommandError('Amount must be greater than 0')

            # Get brand
            try:
                brand = Brand.objects.get(name=brand_name, is_active=True)
            except Brand.DoesNotExist:
                raise CommandError(f'Brand "{brand_name}" not found or inactive')

            # Get campaign
            try:
                campaign = Campaign.objects.get(name=campaign_name, brand=brand, is_active=True)
            except Campaign.DoesNotExist:
                raise CommandError(f'Campaign "{campaign_name}" not found for brand "{brand_name}" or inactive')

            # Record spend via Celery task
            if spend_datetime:
                result = record_spend.delay(brand.id, campaign.id, amount, spend_datetime)
            else:
                result = record_spend.delay(brand.id, campaign.id, amount)

            # Wait for result (since this is a management command)
            task_result = result.get(timeout=30)

            if task_result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully recorded ${amount} spend for campaign "{campaign_name}"\n'
                        f'Daily remaining: ${task_result["daily_remaining"]}\n'
                        f'Monthly remaining: ${task_result["monthly_remaining"]}\n'
                        f'Campaign paused: {task_result["campaign_paused"]}'
                    )
                )
            else:
                raise CommandError(f'Failed to record spend: {task_result["error"]}')

        except Exception as e:
            raise CommandError(f'Error recording spend: {str(e)}')