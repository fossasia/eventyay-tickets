from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pretix.base.forms import I18nModelForm
from pretix.base.models import Device, Room, Gate
from pretix.control.forms import ExtFileField, SplitDateTimeField, SplitDateTimePickerWidget


class RoomForm(I18nModelForm):
    gate = forms.ModelChoiceField(
        queryset=Gate.objects.none(),
        required=False,
        empty_label=_('No gate assigned'),
        help_text=_('Select a gate for this room for session check-ins')
    )
    
    class Meta:
        model = Room
        fields = [
            'name',
            'identifier', 
            'description',
            'location',
            'capacity',
            'session_start',
            'session_end',
            'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'location': forms.TextInput(attrs={'placeholder': _('e.g., Building A, Floor 2, Room 201')}),
            'capacity': forms.NumberInput(attrs={'min': 1, 'max': 10000}),
            'session_start': SplitDateTimePickerWidget(),
            'session_end': SplitDateTimePickerWidget(attrs={'data-date-after': '#id_session_start_0'}),
        }
        field_classes = {
            'session_start': SplitDateTimeField,
            'session_end': SplitDateTimeField,
        }

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)
        
        # Set event after super().__init__ to avoid it being overridden
        self.event = event
        
        # If event is not provided but we have an instance, get event from instance
        if not self.event and self.instance and hasattr(self.instance, 'event'):
            self.event = self.instance.event
        
        if self.event:
            # Set up session time fields
            self.fields['session_start'].required = False
            self.fields['session_end'].required = False
            self.fields['session_start'].help_text = _('When the session in this room starts')
            self.fields['session_end'].help_text = _('When the session in this room ends')
            
            # Set up gate field with one-to-one relationship
            # Show only gates that are not assigned to other rooms
            # Get gates that are already assigned to other rooms (excluding current room)
            other_rooms = Room.objects.filter(
                event=self.event
            ).exclude(
                pk=self.instance.pk if self.instance.pk else None
            )
            assigned_gates = []
            for room in other_rooms:
                assigned_gates.extend(room.gates.values_list('id', flat=True))
            
            # Get all available gate IDs (not assigned to other rooms)
            all_organizer_gates = Gate.objects.filter(
                organizer=self.event.organizer
            ).exclude(
                id__in=assigned_gates
            ).values_list('id', flat=True)
            
            available_gate_ids = list(all_organizer_gates)
            
            # If editing an existing room, include its current gate(s)
            if self.instance.pk and self.instance.gates.exists():
                current_gate_ids = list(self.instance.gates.values_list('id', flat=True))
                # Add current room's gates to available list
                available_gate_ids.extend(current_gate_ids)
                # Set initial value to the first gate
                self.fields['gate'].initial = self.instance.gates.first()
            
            # Create final queryset with all available gate IDs
            self.fields['gate'].queryset = Gate.objects.filter(
                id__in=available_gate_ids
            ).distinct().order_by('name')
        
        # Make identifier optional - it will be auto-generated if not provided
        self.fields['identifier'].required = False
        self.fields['identifier'].help_text = _(
            'A short, unique identifier for this room. If left empty, one will be generated automatically.'
        )
        
        # Set reasonable defaults
        if not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['capacity'].initial = 50

    def clean_identifier(self):
        identifier = self.cleaned_data.get('identifier')
        if identifier:
            # Check for uniqueness within the event
            qs = Room.objects.filter(
                event=self.event,
                identifier=identifier
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise ValidationError(
                    _('A room with this identifier already exists for this event.')
                )
        return identifier

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity is not None and capacity <= 0:
            raise ValidationError(_('Capacity must be greater than 0.'))
        return capacity

    def clean_gate(self):
        gate = self.cleaned_data.get('gate')
        if gate:
            # Check if gate is already assigned to another room
            existing_room = Room.objects.filter(
                event=self.event,
                gates=gate
            ).exclude(pk=self.instance.pk if self.instance.pk else None).first()
            
            if existing_room:
                raise ValidationError(
                    _('Gate "{}" is already assigned to room "{}". Each gate can only be assigned to one room.').format(
                        gate.name, existing_room.name
                    )
                )
        return gate
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Auto-generate identifier if not provided
        if not cleaned_data.get('identifier') and cleaned_data.get('name'):
            base_identifier = cleaned_data['name'].lower().replace(' ', '-')[:20]
            identifier = base_identifier
            counter = 1
            
            while Room.objects.filter(
                event=self.event,
                identifier=identifier
            ).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
                identifier = f"{base_identifier}-{counter}"
                counter += 1
            
            cleaned_data['identifier'] = identifier
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)  # Don't commit yet
        
        # Set the event if not already set
        if not instance.event_id and self.event:
            instance.event = self.event
        
        if commit:
            instance.save()
            
            # Handle gate assignment
            gate = self.cleaned_data.get('gate')
            
            # Clear existing gates
            instance.gates.clear()
            
            # Assign new gate if selected
            if gate:
                instance.gates.add(gate)
        
        return instance



class RoomBulkActionForm(forms.Form):
    """Form for bulk actions on rooms"""
    action = forms.ChoiceField(
        choices=[
            ('activate', _('Activate selected rooms')),
            ('deactivate', _('Deactivate selected rooms')),
            ('export', _('Export room data')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    rooms = forms.ModelMultipleChoiceField(
        queryset=Room.objects.none(),
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)
        
        if event:
            self.fields['rooms'].queryset = Room.objects.filter(
                event=event
            ).order_by('name')