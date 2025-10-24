from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from pretix.base.models import Device, Room, RoomCheckin
from pretix.base.models.log import LogEntry
from pretix.control.forms.event_forms.room_form import RoomForm
from pretix.control.permissions import EventPermissionRequiredMixin


class RoomListView(EventPermissionRequiredMixin, ListView):
    model = Room
    template_name = 'pretixcontrol/event/rooms.html'
    permission = 'can_change_event_settings'
    context_object_name = 'rooms'
    paginate_by = 20

    def get_queryset(self):
        return (
            self.request.event.rooms.all()
            .prefetch_related('checkins')
            .order_by('name')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Add summary statistics
        rooms = self.get_queryset()
        ctx['total_rooms'] = rooms.count()
        ctx['active_rooms'] = rooms.filter(is_active=True).count()
        
        # Calculate total occupancy and capacity
        ctx['total_occupancy'] = sum(room.current_occupancy for room in rooms)
        ctx['total_capacity'] = sum(room.capacity or 0 for room in rooms)
        
        return ctx


class RoomCreateView(EventPermissionRequiredMixin, CreateView):
    model = Room
    template_name = 'pretixcontrol/event/room_edit.html'
    permission = 'can_change_event_settings'
    form_class = RoomForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_success_url(self):
        return reverse(
            'control:event.rooms',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def form_valid(self, form):
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        
        # Exclude 'gate' field from logging since it's handled separately in the form
        log_data = {}
        for k in form.changed_data:
            if k != 'gate' and hasattr(self.object, k):
                log_data[k] = getattr(self.object, k)
        
        form.instance.log_action(
            'pretix.event.room.created',
            user=self.request.user,
            data=log_data,
        )
        messages.success(self.request, _('Room "{name}" has been created.').format(name=self.object.name))
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)


class RoomUpdateView(EventPermissionRequiredMixin, UpdateView):
    model = Room
    template_name = 'pretixcontrol/event/room_edit.html'
    permission = 'can_change_event_settings'
    context_object_name = 'room'
    form_class = RoomForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(
            Room,
            event=self.request.event,
            pk=self.kwargs.get('room')
        )

    def get_success_url(self):
        return reverse(
            'control:event.rooms',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def form_valid(self, form):
        if form.has_changed():
            # Exclude 'gate' field from logging since it's handled separately in the form
            log_data = {}
            for k in form.changed_data:
                if k != 'gate' and hasattr(self.object, k):
                    log_data[k] = getattr(self.object, k)
            
            self.object.log_action(
                'pretix.event.room.changed',
                user=self.request.user,
                data=log_data,
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved.'))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Add room statistics
        ctx['current_occupancy'] = self.object.current_occupancy
        ctx['total_checkins_today'] = RoomCheckin.objects.filter(
            room=self.object,
            type=RoomCheckin.TYPE_ENTRY,
            datetime__date=self.object.event.date_from
        ).count()
        return ctx


class RoomDeleteView(EventPermissionRequiredMixin, DeleteView):
    model = Room
    template_name = 'pretixcontrol/event/room_delete.html'
    permission = 'can_change_event_settings'
    context_object_name = 'room'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Room,
            event=self.request.event,
            pk=self.kwargs.get('room')
        )

    def get_success_url(self):
        return reverse(
            'control:event.rooms',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Check if room has any check-ins
        if self.object.checkins.exists():
            messages.error(
                request,
                _('Cannot delete room "{name}" because it has check-in records.').format(
                    name=self.object.name
                )
            )
            return redirect(self.get_success_url())
        
        # Log the deletion
        self.object.log_action(
            'pretix.event.room.deleted',
            user=self.request.user,
            data={
                'name': self.object.name,
                'identifier': self.object.identifier,
            },
        )
        
        messages.success(
            request,
            _('Room "{name}" has been deleted.').format(name=self.object.name)
        )
        return super().delete(request, *args, **kwargs)


class RoomCheckinsView(EventPermissionRequiredMixin, ListView):
    model = RoomCheckin
    template_name = 'pretixcontrol/event/room_checkins.html'
    permission = 'can_view_orders'
    context_object_name = 'checkins'
    paginate_by = 50

    @cached_property
    def room(self):
        return get_object_or_404(
            Room,
            event=self.request.event,
            pk=self.kwargs.get('room')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['room'] = self.room
        ctx['current_occupancy'] = self.room.current_occupancy
        return ctx

    def get_queryset(self):
        return (
            RoomCheckin.objects.filter(room=self.room)
            .select_related('position', 'position__order', 'device')
            .order_by('-datetime')
        )