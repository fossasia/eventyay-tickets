from django.urls import path
from pretix.api.urls import event_router

from .api import (
    ExhibitorAuthView, ExhibitorInfoViewSet, ExhibitorItemViewSet,
    LeadCreateView, LeadRetrieveView, LeadUpdateView, TagListView,
)
from .views import (
    ExhibitorCopyKeyView, ExhibitorCreateView, ExhibitorDeleteView,
    ExhibitorEditView, ExhibitorListView, SettingsView,
)

urlpatterns = [
    path(
        'control/event/<str:organizer>/<str:event>/settings/exhibitors',
        SettingsView.as_view(),
        name='settings'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/exhibitors',
        ExhibitorListView.as_view(),
        name='info'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/exhibitors/add',
        ExhibitorCreateView.as_view(),
        name='add'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/exhibitors/edit/<int:pk>',
        ExhibitorEditView.as_view(),
        name='edit'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/exhibitors/delete/<int:pk>',
        ExhibitorDeleteView.as_view(),
        name='delete'
    ),
    path(
        'control/event/<str:organizer>/<str:event>/exhibitors/copy_key/<int:pk>',
        ExhibitorCopyKeyView.as_view(),
        name='copy_key'
    ),
    path(
        'api/v1/event/<str:organizer>/<str:event>/exhibitors/auth',
        ExhibitorAuthView.as_view(),
        name='exhibitor-auth'
    ),
    path(
        'api/v1/event/<str:organizer>/<str:event>/exhibitors/lead/create',
        LeadCreateView.as_view(),
        name='lead-create'
    ),
    path(
        'api/v1/event/<str:organizer>/<str:event>/exhibitors/lead/retrieve',
        LeadRetrieveView.as_view(),
        name='lead-retrieve'
    ),
    path(
        'api/v1/event/<str:organizer>/<str:event>/exhibitors/tags',
        TagListView.as_view(),
        name='exhibitor-tags'
    ),
    path(
        'api/v1/event/<str:organizer>/<str:event>/exhibitors/lead/<str:lead_id>/update',
        LeadUpdateView.as_view(),
        name='lead-update'
    ),
]

event_router.register('exhibitors', ExhibitorInfoViewSet, basename='exhibitorinfo')
event_router.register('exhibitoritems', ExhibitorItemViewSet, basename='exhibitoritem')
