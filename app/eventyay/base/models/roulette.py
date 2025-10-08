import uuid

from django.db import models


class RouletteRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    socket_id = models.UUIDField()
    expiry = models.DateTimeField()

    class Meta:
        unique_together = ("socket_id", "room")


class RoulettePairing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    user1 = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="roulette_pairing_left"
    )
    user2 = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="roulette_pairing_right"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
