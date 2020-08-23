import logging

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import get_authorization_header

from venueless.core.models import World
from venueless.core.permissions import Permission
from venueless.core.services.user import login
from venueless.storage.models import StoredFile

logger = logging.getLogger(__name__)

PERMISSIONS_TO_UPLOAD = {
    Permission.WORLD_UPDATE,
    Permission.ROOM_UPDATE,
    Permission.ROOM_CHAT_SEND,
}


class UploadView(View):
    ext_whitelist = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
    )
    max_size = 10 * 1024 * 1024

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def world(self):
        return get_object_or_404(World, domain=self.request.headers["Host"])

    @cached_property
    def user(self):
        # Upload is allowed if the user has update or chat rights in any room
        auth = get_authorization_header(self.request).decode().split()
        if len(auth) != 2:
            raise PermissionDenied()

        if auth[0].lower() == "bearer":
            token = self.world.decode_token(auth[1])
            if not token:
                raise PermissionDenied()
            res = login(world=self.world, token=token)
        elif auth[0].lower() == "client":
            res = login(world=self.world, client_id=auth[1])
        else:
            raise PermissionDenied()
        if not res:
            raise PermissionDenied()

        if any(
            p.value in res.world_config["permissions"] for p in PERMISSIONS_TO_UPLOAD
        ):
            return res.user
        for room in res.world_config["rooms"]:
            if any(p.value in room["permissions"] for p in PERMISSIONS_TO_UPLOAD):
                return res.user
        raise PermissionDenied()

    def post(self, request, *args, **kwargs):
        if not self.user:
            return  # triggers error already

        if "file" not in request.FILES:
            return JsonResponse({"error": "file.missing"}, status=400)

        if request.FILES["file"].size > self.max_size:
            return JsonResponse({"error": "file.size"}, status=400)

        if not any(
            request.FILES["file"].name.lower().endswith(e) for e in self.ext_whitelist
        ):
            return JsonResponse({"error": "file.type"}, status=400)

        sf = StoredFile.objects.create(
            world=self.world,
            date=now(),
            filename=request.FILES["file"].name,
            type=request.FILES["file"].content_type,
            file=request.FILES["file"],
            public=True,
            user=self.user,
        )
        return JsonResponse({"url": sf.file.url}, status=201)
