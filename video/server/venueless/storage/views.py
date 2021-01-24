import logging
from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
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
        ".svg",
    )
    pillow_formats = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
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

        if any(
            request.FILES["file"].name.lower().endswith(e) for e in self.pillow_formats
        ):
            try:
                content_type, file = self.validate_image(request.FILES["file"])
            except ValidationError:
                return JsonResponse({"error": "file.picture.invalid"}, status=400)
        else:
            file = request.FILES["file"]
            content_type = request.FILES["file"].content_type

        sf = StoredFile.objects.create(
            world=self.world,
            date=now(),
            filename=request.FILES["file"].name,
            type=content_type,
            file=file,
            public=True,
            user=self.user,
        )
        return JsonResponse({"url": sf.file.url}, status=201)

    def validate_image(self, data):
        # partially vendored from django.forms.fields.ImageField
        # We need to get a file object for Pillow. We might have a path or we might
        # have to read the data into memory.
        if hasattr(data, "temporary_file_path"):
            file = data.temporary_file_path()
        else:
            if hasattr(data, "read"):
                file = BytesIO(data.read())
            else:
                file = BytesIO(data["content"])

        try:
            # load() could spot a truncated JPEG, but it loads the entire
            # image in memory, which is a DoS vector. See #3848 and #18520.
            image = Image.open(file)
            # verify() must be called immediately after the constructor.
            image.verify()
        except Exception:
            # Pillow doesn't recognize it as an image.
            raise ValidationError("invalid image")

        file.seek(0)
        o = BytesIO()
        o.name = data.name
        image = Image.open(file)
        image_without_exif = Image.new(image.mode, image.size)
        image_without_exif.putdata(image.getdata())
        image_without_exif.save(o)
        o.seek(0)
        return Image.MIME.get(image.format), File(o, name=data.name)
