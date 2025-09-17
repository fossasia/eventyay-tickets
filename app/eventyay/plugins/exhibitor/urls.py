from django.urls import include, path

from . import views

app_name = 'exhibitor'

# Admin/Control URLs
control_patterns = [
    path('', views.ExhibitorListView.as_view(), name='index'),
    path('list/', views.ExhibitorListView.as_view(), name='list'),
    path('create/', views.ExhibitorCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ExhibitorDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ExhibitorEditView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.ExhibitorDeleteView.as_view(), name='delete'),
    path('<int:pk>/key/', views.ExhibitorCopyKeyView.as_view(), name='copy-key'),
    path('leads/', views.LeadListView.as_view(), name='leads'),
    path('leads/export/', views.LeadExportView.as_view(), name='leads-export'),
    path('settings/', views.ExhibitorSettingsView.as_view(), name='settings'),
]

# API URLs
api_patterns = [
    path('auth/', views.ExhibitorAuthView.as_view(), name='api-auth'),
    path('exhibitors/', views.ExhibitorAPIListView.as_view(), name='api-exhibitors'),
    path('exhibitors/<int:pk>/', views.ExhibitorAPIDetailView.as_view(), name='api-exhibitor-detail'),
    path('leads/', views.LeadCreateView.as_view(), name='api-lead-create'),
    path('leads/list/', views.LeadRetrieveView.as_view(), name='api-lead-list'),
    path('leads/<str:lead_id>/', views.LeadUpdateView.as_view(), name='api-lead-update'),
    path('tags/', views.TagListView.as_view(), name='api-tags'),
]

urlpatterns = [
    path('control/', include(control_patterns)),
    path('api/', include(api_patterns)),
]