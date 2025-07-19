import logging
from io import BytesIO

from asgiref.sync import async_to_sync
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, ImageOps
from PIL.Image import Resampling
from rest_framework.authentication import get_authorization_header

from eventyay.base.models import Event
from eventyay.core.permissions import Permission
from eventyay.base.services.user import AuthError, login
from eventyay.base.services.event import notify_schedule_change
from eventyay.base.models.storage_model import StoredFile
from eventyay.storage.schedule_to_json import convert

logger = logging.getLogger(__name__)


class UploadMixin:
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def event(self):
        event_id = self.kwargs.get("event_id", None)
        return get_object_or_404(Event, id=event_id)

    @cached_property
    def user(self):
        # Upload is allowed if the user has update or chat rights in any room
        auth = get_authorization_header(self.request).decode().split()
        if len(auth) != 2:
            raise PermissionDenied()

        if auth[0].lower() == "bearer":
            token = self.event.decode_token(auth[1])
            if not token:
                raise PermissionDenied()
            try:
                res = login(event=self.event, token=token)
            except AuthError:
                raise PermissionDenied()
        elif auth[0].lower() == "client":
            try:
                res = login(event=self.event, client_id=auth[1])
            except AuthError:
                raise PermissionDenied()
        else:
            raise PermissionDenied()

        if any(p.value in res.event_config["permissions"] for p in self.permissions):
            return res.user
        for room in res.event_config["rooms"]:
            if any(p.value in room["permissions"] for p in self.permissions):
                return res.user
        raise PermissionDenied()


def get_sizes(size, imgsize):
    wfactor = min(1, size[0] / imgsize[0])
    hfactor = min(1, size[1] / imgsize[1])

    if wfactor == hfactor:
        return int(imgsize[0] * hfactor), int(imgsize[1] * wfactor)
    elif wfactor < hfactor:
        return size[0], int(imgsize[1] * wfactor)
    else:
        return int(imgsize[0] * hfactor), size[1]


def resize_image(image, size):
    new_size = get_sizes(size, image.size)
    image = image.resize(new_size, resample=Resampling.LANCZOS)
    return image


class UploadView(UploadMixin, View):
    permissions = {
        Permission.EVENT_VIEW,
        Permission.EVENT_UPDATE,
        Permission.ROOM_UPDATE,
        Permission.ROOM_CHAT_SEND,
    }
    ext_whitelist = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".svg",
        ".mp4",
        ".webm",
        ".mp3",
    )
    pillow_formats = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
    )
    max_size = 10 * 1024 * 1024

    def post(self, request, *args, **kwargs):
        if not self.user:
            return  # triggers error already

        if "file" not in request.FILES:
            return JsonResponse({"error": "file.missing"}, status=400)

        if not any(
            request.FILES["file"].name.lower().endswith(e) for e in self.ext_whitelist
        ):
            return JsonResponse({"error": "file.type"}, status=400)

        if any(
            request.FILES["file"].name.lower().endswith(e) for e in self.pillow_formats
        ):
            try:
                content_type, file, size = self.validate_image(request.FILES["file"])
            except ValidationError:
                return JsonResponse({"error": "file.picture.invalid"}, status=400)
        else:
            file = request.FILES["file"]
            content_type = request.FILES["file"].content_type
            size = request.FILES["file"].size

        if size > self.max_size:
            return JsonResponse({"error": "file.size"}, status=400)

        sf = StoredFile.objects.create(
            event=self.event,
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

        if hasattr(file, "seek"):
            file.seek(0)

        image = original_image = Image.open(file)
        image_modified = False

        # before we resize or resave anything
        if image.format == "JPEG":
            image = ImageOps.exif_transpose(image)
            image_modified = True

        if self.request.POST.get("width") and self.request.POST.get("height"):
            try:
                image = resize_image(
                    original_image,
                    (
                        int(self.request.POST.get("width")),
                        int(self.request.POST.get("height")),
                    ),
                )
                image_modified = True
            except ValueError:
                pass

        o = BytesIO()
        o.name = data.name
        if image.format == "JPEG":
            image_without_exif = Image.new(image.mode, image.size)
            image_without_exif.putdata(image.getdata())
            image_without_exif.save(
                o, format="JPEG", quality=95
            )  # Pillow's default JPEG quality is 75
        elif not image_modified:
            size = len(data)
            if hasattr(data, "seek"):
                data.seek(0)
            return Image.MIME.get(image.format), data, size
        else:
            image.save(o, format=original_image.format)

        o.seek(0)
        return (
            Image.MIME.get(original_image.format),
            File(o, name=data.name),
            len(o.getvalue()),
        )


class ScheduleImportView(UploadMixin, View):
    permissions = {Permission.EVENT_UPDATE}
    ext_whitelist = (".xlsx",)
    max_size = 2 * 1024 * 1024

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

        try:
            jsondata = convert(request.FILES["file"], timezone=self.event.timezone)
        except ValidationError as e:
            return JsonResponse({"error": ", ".join(e)}, status=400)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        sf = StoredFile.objects.create(
            event=self.event,
            date=now(),
            filename=f'schedule_{now().strftime("%Y-%m-%d-%H-%M-%S")}.json',
            type="application/json",
            file=ContentFile(jsondata, "schedule.json"),
            public=True,
            user=self.user,
        )
        async_to_sync(notify_schedule_change)(self.event.id)
        return JsonResponse({"url": sf.file.url}, status=201)
