from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api, views

# API Router
router = DefaultRouter()
router.register(r'exhibitors', api.ExhibitorViewSet, basename='exhibitor')
router.register(r'exhibitor-settings', api.ExhibitorSettingsViewSet, basename='exhibitor-settings')
router.register(r'contact-requests', api.ContactRequestViewSet, basename='contact-request')
router.register(r'leads', api.LeadViewSet, basename='lead')

app_name = 'exhibitors'

# Frontend URL patterns
frontend_patterns = [
    path('', views.ExhibitorDirectoryView.as_view(), name='directory'),
    path('<str:booth_id>/', views.ExhibitorDetailView.as_view(), name='detail'),
    path('management/', views.ExhibitorManagementView.as_view(), name='management'),
    path('management/create/', views.ExhibitorCreateView.as_view(), name='create'),
    path('management/<int:pk>/edit/', views.ExhibitorEditView.as_view(), name='edit'),
    path('management/<int:pk>/delete/', views.ExhibitorDeleteView.as_view(), name='delete'),
    
    # AJAX endpoints for frontend
    path('ajax/search/', views.ExhibitorSearchView.as_view(), name='ajax-search'),
    path('ajax/<int:pk>/contact/', views.ExhibitorContactView.as_view(), name='ajax-contact'),
    path('ajax/<int:pk>/analytics/', views.ExhibitorAnalyticsView.as_view(), name='ajax-analytics'),
]

# API URL patterns
api_patterns = [
    path('v1/', include(router.urls)),
]

# Main URL patterns (used when included with 'exhibitors' namespace)
urlpatterns = frontend_patterns