from django.urls import path
from . import views

app_name = 'budget_system'

urlpatterns = [
    # Spend recording endpoint
    path('api/spend/', views.RecordSpendView.as_view(), name='record_spend'),
    
    # Campaign management endpoints
    path('api/campaigns/<int:campaign_id>/status/', views.CampaignStatusView.as_view(), name='campaign_status'),
    path('api/campaigns/<int:campaign_id>/toggle/', views.CampaignToggleView.as_view(), name='campaign_toggle'),
    
    # Brand status endpoint
    path('api/brands/<int:brand_id>/status/', views.BrandStatusView.as_view(), name='brand_status'),
]