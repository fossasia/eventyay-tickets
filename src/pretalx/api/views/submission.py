import datetime as dt
import json
import logging

import jwt
import requests
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django_filters import rest_framework as filters
from django_scopes import scopes_disabled
from rest_framework import status, viewsets
from rest_framework.authentication import get_authorization_header

from pretalx.api.serializers.submission import (
    ScheduleListSerializer,
    ScheduleSerializer,
    SubmissionOrgaSerializer,
    SubmissionReviewerSerializer,
    SubmissionSerializer,
    TagSerializer,
)
from pretalx.common import exceptions
from pretalx.person.models import User
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission, SubmissionStates, Tag
from pretalx.submission.models.submission import (
    SubmissionFavourite,
    SubmissionFavouriteSerializer,
)

with scopes_disabled():

    class SubmissionFilter(filters.FilterSet):
        state = filters.MultipleChoiceFilter(choices=SubmissionStates.get_choices())

        class Meta:
            model = Submission
            fields = ("state", "content_locale", "submission_type", "is_featured")


logger = logging.getLogger(__name__)


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubmissionSerializer
    queryset = Submission.objects.none()
    lookup_field = "code__iexact"
    search_fields = ("title", "speakers__name")
    filterset_class = SubmissionFilter

    def get_queryset(self):
        if self.request._request.path.endswith(
            "/talks/"
        ) or not self.request.user.has_perm(
            "orga.view_submissions", self.request.event
        ):
            if (
                not self.request.user.has_perm(
                    "agenda.view_schedule", self.request.event
                )
                or not self.request.event.current_schedule
            ):
                return Submission.objects.none()
            return self.request.event.submissions.filter(
                pk__in=self.request.event.current_schedule.talks.filter(
                    is_visible=True
                ).values_list("submission_id", flat=True)
            )
        return self.request.event.submissions.all()

    def get_serializer_class(self):
        if self.request.user.has_perm("orga.change_submissions", self.request.event):
            return SubmissionOrgaSerializer
        if self.request.user.has_perm("orga.view_submissions", self.request.event):
            return SubmissionReviewerSerializer
        return SubmissionSerializer

    @cached_property
    def serializer_questions(self):
        return (self.request.query_params.get("questions") or "").split(",")

    def get_serializer(self, *args, **kwargs):
        can_view_speakers = self.request.user.has_perm(
            "agenda.view_schedule", self.request.event
        ) or self.request.user.has_perm("orga.view_speakers", self.request.event)
        if self.request.query_params.get("anon"):
            can_view_speakers = False
        return super().get_serializer(
            *args,
            can_view_speakers=can_view_speakers,
            event=self.request.event,
            questions=self.serializer_questions,
            **kwargs,
        )


class ScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleSerializer
    queryset = Schedule.objects.none()
    lookup_value_regex = "[^/]+"

    def get_serializer_class(self):
        if self.action == "list":
            return ScheduleListSerializer
        return ScheduleSerializer  # self.action == 'retrieve'

    def get_object(self):
        schedules = self.get_queryset()
        query = self.kwargs.get(self.lookup_field)
        if query == "wip":
            schedule = schedules.filter(version__isnull=True).first()
        else:
            if query == "latest" and self.request.event.current_schedule:
                query = self.request.event.current_schedule.version
            schedule = schedules.filter(version__iexact=query).first()
        if not schedule:
            raise Http404
        return schedule

    def get_queryset(self):
        qs = self.queryset
        is_public = (
            self.request.event.is_public
            and self.request.event.feature_flags["show_schedule"]
        )
        current_schedule = (
            self.request.event.current_schedule.pk
            if self.request.event.current_schedule
            else None
        )
        if self.request.user.has_perm("orga.view_schedule", self.request.event):
            return self.request.event.schedules.all()
        if is_public:
            return self.request.event.schedules.filter(pk=current_schedule)
        return qs


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.none()
    lookup_field = "tag__iexact"

    def get_queryset(self):
        if self.request.user.has_perm("orga.view_submissions", self.request.event):
            return self.request.event.tags.all()
        return Tag.objects.none()


class SubmissionFavouriteView(View):
    """
    A view for handling user's favourite talks.

    - GET: Retrieve the list of favourite talks for the authenticated user.
    - PUT: Add talks to the user's favourite list.
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs) -> JsonResponse:
        """
        Handle GET requests to retrieve the list of favourite talks
        """
        try:
            user_id = request.user.id
            # user_id = 52
            fav_talks = get_object_or_404(SubmissionFavourite, user=user_id)
            return JsonResponse(fav_talks.talk_list, safe=False)
        except Http404:
            # As user not have any favourite talk yet
            return JsonResponse([], safe=False)
        except Exception as e:
            logger.error(f"unexpected error happened: {str(e)}")
            return JsonResponse(
                {"error": str(e)},
                safe=False,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @staticmethod
    def post(request, *args, **kwargs) -> JsonResponse:
        """
        Handle POST requests to add talks to the user's favourite list.
        """
        try:
            user_id = request.user.id
            if user_id is None:
                user_id = SubmissionFavouriteView.get_user_from_token(
                    request, request.event.venueless_settings
                )
            talk_list = json.loads(request.body.decode())
            talk_list_valid = []
            for talk in talk_list:
                with scopes_disabled():
                    if Submission.objects.filter(code=talk).exists():
                        talk_list_valid.append(talk)

            data = {"user": user_id, "talk_list": talk_list_valid}
            serializer = SubmissionFavouriteSerializer(data=data)
            if serializer.is_valid():
                fav_talks = serializer.save(user_id, talk_list_valid)
                # call to video for update favourite talks
                token = SubmissionFavouriteView.get_user_video_token(
                    request.user.code, request.event.venueless_settings
                )
                video_url = request.event.venueless_settings.url + "favourite-talk/"
                header = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                }
                requests.post(
                    video_url, data=json.dumps(talk_list_valid), headers=header
                )
            else:
                logger.error(f"Validation error: {serializer.errors}")
                return JsonResponse(
                    {"error": serializer.errors},
                    safe=False,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return JsonResponse(
                fav_talks.talk_list, safe=False, status=status.HTTP_200_OK
            )

        except Http404:
            logger.info("User not login yet, so can't add favourite talks.")
            return JsonResponse(
                "user_not_logged_in", safe=False, status=status.HTTP_400_BAD_REQUEST
            )
        except IntegrityError as e:
            logger.error(f"Integrity error: {str(e)}")
            return JsonResponse(
                {"error": str(e)}, safe=False, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                {"error": str(e)},
                safe=False,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @staticmethod
    def get_user_video_token(user_code, video_settings):
        iat = dt.datetime.utcnow()
        exp = iat + dt.timedelta(days=30)
        payload = {
            "iss": video_settings.issuer,
            "aud": video_settings.audience,
            "exp": exp,
            "iat": iat,
            "uid": user_code,
        }
        token = jwt.encode(payload, video_settings.secret, algorithm="HS256")
        return token

    @staticmethod
    def get_user_from_token(request, video_settings):
        auth_header = get_authorization_header(request).split()
        if not auth_header:
            raise Http404
        if auth_header and auth_header[0].lower() == b"bearer":
            if len(auth_header) == 1:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. No credentials provided."
                )
            elif len(auth_header) > 2:
                raise exceptions.AuthenticationFailed(
                    "Invalid token header. Token string should not contain spaces."
                )
        token_decode = jwt.decode(
            auth_header[1],
            video_settings.secret,
            algorithms=["HS256"],
            audience=video_settings.audience,
            issuer=video_settings.issuer,
        )
        user_code = token_decode.get("uid")
        return get_object_or_404(User, code=user_code).id
