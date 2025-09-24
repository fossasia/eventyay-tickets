import logging

from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.views import View

from eventyay.cfp.views.event import EventPageMixin
from eventyay.common.exceptions import SendMailException
from eventyay.common.text.phrases import phrases

logger = logging.getLogger(__name__)


class SubmitStartView(EventPageMixin, View):
    @staticmethod
    def get(request, *args, **kwargs):
        url = reverse(
            "cfp:event.submit",
            kwargs={
                "event": request.event.slug,
                "step": list(request.event.cfp_flow.steps_dict.keys())[0],
                "tmpid": get_random_string(length=6),
            },
        )
        if request.GET:
            url += f"?{request.GET.urlencode()}"
        return redirect(url)


class SubmitWizard(EventPageMixin, View):
    @transaction.atomic
    def dispatch(self, request, *args, **kwargs):
        self.event = self.request.event
        request.access_code = None
        if access_code := request.GET.get("access_code"):
            access_code = request.event.submitter_access_codes.filter(
                code__iexact=access_code
            ).first()
            if access_code and access_code.is_valid:
                request.access_code = access_code
        if not request.event.cfp.is_open and not request.access_code:
            messages.error(request, _("Proposals are closed"))
            return redirect(
                reverse("cfp:event.start", kwargs={"event": request.event.slug})
            )
        step = None
        for step in request.event.cfp_flow.steps:
            if not step.is_applicable(request):
                continue
            if step.identifier == kwargs["step"]:
                break
            step.is_before = True
            step.resolved_url = step.get_step_url(request)
        if getattr(step, "is_before", False):  # The current step URL is incorrect
            raise Http404()
        handler = getattr(step, request.method.lower(), self.http_method_not_allowed)
        logger.debug("Handler: %s", handler)
        result = handler(request)

        if request.method == "POST" and request.POST.get("action", "submit") == "draft":
            return self.done(
                request,
                draft=True,
                steps=[
                    step
                    for step in request.event.cfp_flow.steps
                    if getattr(step, "is_before", False)
                    or step.identifier == kwargs["step"]
                    or step.identifier == "user"
                ],
            )
        if request.method == "GET" or (
            step.get_next_applicable(request) or not step.is_completed(request)
        ):
            if result and (csp_change := step.get_csp_update(request)):
                result._csp_update = csp_change
            return result
        return self.done(request)

    def done(self, request, draft=False, steps=None):
        # We are done, or at least we finished the last step. Time to check results.
        valid_steps = []
        steps = steps or request.event.cfp_flow.steps
        for step in steps:
            if step.is_applicable(request):
                if not step.is_completed(request):
                    query = {"draft": 1} if draft else None
                    return redirect(step.get_step_url(request, query=query))
                valid_steps.append(step)

        # We are done, or at least the data checks out. Time to save results.
        request.event.cfp_flow.steps_dict["user"].done(request)
        for step in valid_steps:
            if step.identifier != "user":
                step.done(request, draft=draft)

        if not draft:
            try:
                request.submission.send_initial_mails(person=request.user)
            except SendMailException as exception:
                logging.getLogger("").warning(str(exception))
                messages.warning(request, phrases.cfp.submission_email_fail)

        return redirect(
            reverse("cfp:event.user.submissions", kwargs={"event": request.event.slug})
        )
