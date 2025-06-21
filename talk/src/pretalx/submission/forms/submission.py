from django import forms
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes.forms import SafeModelChoiceField

from pretalx.cfp.forms.cfp import CfPFormMixin
from pretalx.common.forms.fields import ImageField
from pretalx.common.forms.mixins import PublicContent, RequestRequire
from pretalx.common.forms.renderers import InlineFormRenderer
from pretalx.common.forms.widgets import (
    EnhancedSelect,
    MarkdownWidget,
    SearchInput,
    SelectMultipleWithCount,
)
from pretalx.common.text.phrases import phrases
from pretalx.common.views.mixins import Filterable
from pretalx.submission.models import (
    Answer,
    Question,
    Submission,
    SubmissionStates,
    Tag,
    Track,
)


class InfoForm(CfPFormMixin, RequestRequire, PublicContent, forms.ModelForm):
    additional_speaker = forms.EmailField(
        label=_("Additional Speaker"),
        help_text=_(
            "If you have a co-speaker, please add their email address here, and we will invite them to create an account. If you have more than one co-speaker, you can add more speakers after finishing the proposal process."
        ),
        required=False,
    )
    image = ImageField(
        required=False,
        label=_("Session image"),
        help_text=_("Use this if you want an illustration to go with your proposal."),
    )
    content_locale = forms.ChoiceField(label=phrases.base.language)

    def __init__(self, event, remove_additional_speaker=False, **kwargs):
        self.event = event
        self.readonly = kwargs.pop("readonly", False)
        self.access_code = kwargs.pop("access_code", None)
        self.default_values = {}
        instance = kwargs.get("instance")
        initial = kwargs.pop("initial", {}) or {}
        if not instance or not instance.submission_type:
            initial["submission_type"] = (
                getattr(self.access_code, "submission_type", None)
                or initial.get("submission_type")
                or self.event.cfp.default_type
            )
        if not instance and self.access_code:
            initial["track"] = self.access_code.track
        if not instance or not instance.content_locale:
            initial["content_locale"] = self.event.locale

        super().__init__(initial=initial, **kwargs)

        if remove_additional_speaker and "additional_speaker" in self.fields:
            self.fields.pop("additional_speaker")
        if "abstract" in self.fields:
            self.fields["abstract"].widget.attrs["rows"] = 2

        self._set_track(instance=instance)
        self._set_submission_types(instance=instance)
        self._set_locales()
        self._set_slot_count(instance=instance)

        if self.readonly:
            for field in self.fields.values():
                field.disabled = True

    def _set_track(self, instance=None):
        if "track" in self.fields:
            if (
                not self.event.get_feature_flag("use_tracks")
                or instance
                and instance.state != SubmissionStates.SUBMITTED
            ):
                self.fields.pop("track")
                return

            access_code = self.access_code or getattr(instance, "access_code", None)
            if not access_code or not access_code.track:
                track_filter = self.event.tracks.filter(requires_access_code=False)
                # ensure current track selection can be preserved
                if instance and instance.track and instance.track.requires_access_code:
                    track_filter = self.event.tracks.filter(
                        Q(requires_access_code=False) | Q(pk=instance.track.pk)
                    )

                self.fields["track"].queryset = track_filter
            else:
                self.fields["track"].queryset = self.event.tracks.filter(
                    pk=access_code.track.pk
                )
            if (
                len(self.fields["track"].queryset) == 1
                and self.fields["track"].required
            ):
                self.default_values["track"] = self.fields["track"].queryset.first()
                self.fields.pop("track")

    def _set_submission_types(self, instance=None):
        _now = now()
        submission_types = self.event.submission_types
        if (
            instance
            and instance.pk
            and (
                instance.state != SubmissionStates.SUBMITTED
                or not self.event.cfp.is_open
            )
        ):
            self.fields["submission_type"].queryset = submission_types.filter(
                pk=instance.submission_type_id
            )
            self.fields["submission_type"].disabled = True
            return
        access_code = self.access_code or getattr(instance, "access_code", None)
        if access_code and not access_code.submission_type:
            pks = set(submission_types.values_list("pk", flat=True))
        elif access_code:
            pks = {access_code.submission_type.pk}
        else:
            queryset = submission_types.filter(requires_access_code=False)
            if not self.event.cfp.deadline or self.event.cfp.deadline >= _now:
                # No global deadline or still open
                types = queryset.exclude(deadline__lt=_now)
            else:
                types = queryset.filter(deadline__gte=_now)
            pks = set(types.values_list("pk", flat=True))
        if instance and instance.pk:
            pks |= {instance.submission_type.pk}
        if len(pks) == 1:
            self.default_values["submission_type"] = submission_types.get(
                pk=list(pks)[0]
            )
            self.fields.pop("submission_type")
        else:
            self.fields["submission_type"].queryset = submission_types.filter(
                pk__in=pks
            )
            if "duration" in self.fields and not self.fields["duration"].required:
                self.fields["duration"].help_text += " " + str(
                    _("Leave empty to use the default duration for the session type.")
                )

    def _set_locales(self):
        if "content_locale" in self.fields:
            if len(self.event.content_locales) == 1:
                self.default_values["content_locale"] = self.event.content_locales[0]
                self.fields.pop("content_locale")
            else:
                self.fields["content_locale"].choices = self.event.named_content_locales

    def _set_slot_count(self, instance=None):
        if not self.event.get_feature_flag("present_multiple_times"):
            self.fields.pop("slot_count", None)
        elif (
            "slot_count" in self.fields
            and instance
            and instance.state in SubmissionStates.accepted_states
        ):
            self.fields["slot_count"].disabled = True
            self.fields["slot_count"].help_text += " " + str(
                _(
                    "Please contact the organisers if you want to change how often you’re presenting this proposal."
                )
            )

    def save(self, *args, **kwargs):
        for key, value in self.default_values.items():
            setattr(self.instance, key, value)
        result = super().save(*args, **kwargs)
        if "image" in self.cleaned_data:
            self.instance.process_image("image")
        return result

    class Meta:
        model = Submission
        fields = [
            "title",
            "submission_type",
            "track",
            "content_locale",
            "abstract",
            "description",
            "notes",
            "slot_count",
            "do_not_record",
            "image",
            "duration",
        ]
        request_require = [
            "title",
            "abstract",
            "description",
            "notes",
            "image",
            "do_not_record",
            "track",
            "duration",
            "content_locale",
            "additional_speaker",
        ]
        public_fields = ["title", "abstract", "description", "image"]
        widgets = {
            "abstract": MarkdownWidget,
            "description": MarkdownWidget,
            "notes": MarkdownWidget,
            "track": EnhancedSelect(
                description_field="description", color_field="color"
            ),
        }
        field_classes = {
            "submission_type": SafeModelChoiceField,
            "track": SafeModelChoiceField,
        }


class CountableOption:
    def __init__(self, name, count):
        self.name = name
        self.count = count

    def __str__(self):
        return str(self.name)


class SubmissionFilterForm(forms.Form):
    state = forms.MultipleChoiceField(
        required=False,
        choices=[
            (state, name)
            for (state, name) in SubmissionStates.get_choices()
            if state not in (SubmissionStates.DELETED, SubmissionStates.DRAFT)
        ],
        widget=SelectMultipleWithCount(
            attrs={"title": _("Proposal states")},
            color_field=SubmissionStates.get_color,
        ),
    )
    submission_type = forms.MultipleChoiceField(
        required=False,
        widget=SelectMultipleWithCount(attrs={"title": _("Session types")}),
    )
    pending_state__isnull = forms.BooleanField(
        required=False,
        label=_("exclude pending"),
    )
    content_locale = forms.MultipleChoiceField(
        required=False,
        widget=SelectMultipleWithCount(attrs={"title": phrases.base.language}),
    )
    track = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Track.objects.none(),
        widget=SelectMultipleWithCount(
            attrs={"title": _("Tracks")}, color_field="color"
        ),
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
        widget=SelectMultipleWithCount(attrs={"title": _("Tags")}, color_field="color"),
    )
    question = SafeModelChoiceField(queryset=Question.objects.none(), required=False)
    unanswered = forms.BooleanField(required=False)
    answer = forms.CharField(required=False)
    answer__options = forms.IntegerField(required=False)
    q = forms.CharField(required=False, label=_("Search"), widget=SearchInput)

    default_renderer = InlineFormRenderer

    def __init__(self, event, *args, limit_tracks=False, search_fields=None, **kwargs):
        self.event = event
        self.search_fields = search_fields or (
            "code__icontains",
            "title__icontains",
            "speakers__name__icontains",
        )
        usable_states = kwargs.pop("usable_states", None)
        initial = kwargs.pop("initial", {}) or {}
        initial["exclude_pending"] = False
        super().__init__(*args, initial=initial, **kwargs)
        qs = event.submissions
        state_qs = Submission.objects.filter(event=event)
        if usable_states:
            qs = qs.filter(state__in=usable_states)
            state_qs = state_qs.filter(state__in=usable_states)
        state_count = {
            d["state"]: d["state__count"]
            for d in state_qs.order_by("state").values("state").annotate(Count("state"))
        }
        state_count.update(
            {
                f"pending_state__{d['pending_state']}": d["pending_state__count"]
                for d in state_qs.filter(pending_state__isnull=False)
                .order_by("pending_state")
                .values("pending_state")
                .annotate(Count("pending_state"))
            }
        )
        sub_types = event.submission_types.all()
        if limit_tracks and isinstance(limit_tracks, (list, tuple, set)):
            limit_tracks = event.tracks.filter(
                pk__in=[track.pk for track in limit_tracks]
            )
        tracks = limit_tracks or event.tracks.all()
        languages = event.named_content_locales
        if len(sub_types) > 1:
            type_count = {
                d["submission_type_id"]: d["submission_type_id__count"]
                for d in qs.order_by("submission_type_id")
                .values("submission_type_id")
                .annotate(Count("submission_type_id"))
            }
            self.fields["submission_type"].choices = [
                (
                    sub_type.pk,
                    CountableOption(sub_type.name, type_count.get(sub_type.pk, 0)),
                )
                for sub_type in sub_types
            ]
        else:
            self.fields.pop("submission_type", None)
        if len(tracks) > 1:
            self.fields["track"].queryset = tracks.annotate(
                count=Count(
                    "submissions",
                    distinct=True,
                    filter=Q(event=event)
                    & ~Q(
                        submissions__state__in=[
                            SubmissionStates.DELETED,
                            SubmissionStates.DRAFT,
                        ]
                    ),
                )
            ).order_by("-count")
        else:
            self.fields.pop("track", None)
        if len(languages) > 1:
            language_count = {
                d["content_locale"]: d["content_locale__count"]
                for d in qs.order_by("content_locale")
                .values("content_locale")
                .annotate(Count("content_locale"))
            }
            self.fields["content_locale"].choices = [
                (code, CountableOption(name, language_count.get(code, 0)))
                for code, name in languages
            ]
        else:
            self.fields.pop("content_locale", None)

        if not self.event.tags.all().exists():
            self.fields.pop("tags", None)
        else:
            self.fields["tags"].queryset = event.tags.prefetch_related(
                "submissions"
            ).annotate(submission_count=Count("submissions", distinct=True))

        if usable_states:
            usable_states = [
                choice
                for choice in self.fields["state"].choices
                if choice[0] in usable_states
            ]
        else:
            usable_states = self.fields["state"].choices
        usable_states += [
            (
                f"pending_state__{choice[0]}",
                str(_("Pending {state}")).format(state=choice[1]),
            )
            for choice in usable_states
        ]
        self.fields["state"].choices = [
            (
                choice[0],
                CountableOption(choice[1].capitalize(), state_count.get(choice[0], 0)),
            )
            for choice in usable_states
        ]
        self.fields["question"].queryset = event.questions.all()

    def _filter_question(
        self, qs, question=None, answer=None, option=None, unanswered=False
    ):
        if question and (answer or option):
            if option:
                option = option.pk if hasattr(option, "pk") else option
                answers = Answer.objects.filter(
                    submission_id=OuterRef("pk"),
                    question_id=question,
                    options__pk=option,
                )
            else:
                answers = Answer.objects.filter(
                    submission_id=OuterRef("pk"),
                    question_id=question,
                    answer__exact=answer,
                )
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=True)
        elif question and unanswered:
            answers = Answer.objects.filter(
                question_id=question, submission_id=OuterRef("pk")
            )
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=False)
        return qs

    def filter_queryset(self, qs):
        for field in ("submission_type", "content_locale", "track", "tags"):
            value = self.cleaned_data.get(field)
            if value:
                qs = qs.filter(**{f"{field}__in": value})

        state_filter = self.cleaned_data.get("state")
        if state_filter:
            states = [
                state
                for state in state_filter
                if not state.startswith("pending_state__")
            ]
            pending_states = [
                state.split("__")[1] for state in state_filter if state not in states
            ]
            if states and not pending_states:
                qs = qs.filter(state__in=states)
            elif pending_states and not states:
                qs = qs.filter(pending_state__in=pending_states)
            else:
                qs = qs.filter(
                    Q(state__in=states) | Q(pending_state__in=pending_states)
                )

        if self.cleaned_data.get("pending_state__isnull"):
            qs = qs.filter(pending_state__isnull=True)

        search = self.cleaned_data.get("q")
        if search:
            qs = Filterable.handle_search(qs, search, self.search_fields)

        qs = self._filter_question(
            qs,
            question=self.cleaned_data.get("question"),
            answer=self.cleaned_data.get("answer"),
            option=self.cleaned_data.get("answer__options"),
            unanswered=self.cleaned_data.get("unanswered"),
        )
        if not self.cleaned_data.get("state"):
            qs = qs.exclude(state="deleted")
        return qs
