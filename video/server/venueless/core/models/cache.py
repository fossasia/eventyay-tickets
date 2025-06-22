import logging
import os
import random
import time

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from django.core.cache import caches
from django.db import models, transaction

from venueless.core.utils.redis import aredis

SETIFHIGHER = """local c = tonumber(redis.call('get', KEYS[1]));
if c then
    if tonumber(ARGV[1]) > c then
        redis.call('set', KEYS[1], ARGV[1]);
        redis.call('expire', KEYS[1], 604800);
        return tonumber(ARGV[1])
    else
        return tonumber(c)
    end
else
    redis.call('set', KEYS[1], ARGV[1]);
    redis.call('expire', KEYS[1], 604800);
    return tonumber(ARGV[1])
end"""  # 604800 seconds = 7 days

logger = logging.getLogger(__name__)


class VersionedModel(models.Model):
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__refresh_time = time.time()
        self.clear_caches()

    def save(self, *args, **kwargs):
        if "update_fields" in kwargs and "version" not in kwargs.get("update_fields"):
            kwargs["update_fields"].append("version")
        self.version += 1
        r = super().save(*args, **kwargs)
        transaction.on_commit(async_to_sync(self._set_cache_version))
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        transaction.on_commit(async_to_sync(self._set_cache_deleted))
        return r

    def touch(self):
        self.save(update_fields=["version"])
        self.clear_caches()

    async def refresh_from_db_if_outdated(self, allowed_age=0):
        if allowed_age:
            # In some places, we allow the cache to be a little outdated to avoid thousands
            # of GET calls to redis. We add some random variance to the duration to soften
            # load spikes if all threads force-refreshed at the same time. We also do not do
            # this during unit testing, which is bad (since it means tests are different from
            # the real world) but also necessary if we don't want to have long sleep() calls
            # in our tests.
            if (
                time.time() - self.__refresh_time
                < allowed_age * random.uniform(0.7, 1.3)
                and "PYTEST_CURRENT_TEST" not in os.environ
            ):
                return

        async with aredis(self._cachekey) as redis:
            latest_version = await redis.get(f"{self._cachekey}:version")
        if latest_version:
            if latest_version == b"deleted":
                raise self.__class__.DoesNotExist
            latest_version = int(latest_version.decode())
        else:
            latest_version = 0

        if latest_version == self.version:
            return

        cache = caches["process"]
        cached_instance = cache.get(self._cachekey)
        if cached_instance and cached_instance.version == latest_version:
            self._refresh_from_cache(cached_instance)
            return

        await database_sync_to_async(self.refresh_from_db)()
        cache.set(self._cachekey, self, timeout=600)
        if latest_version < self.version:
            await self._set_cache_version()

    def clear_caches(self):
        pass

    @property
    def _cachekey(self):
        return f"modelcache:{self._meta.label}:{self.pk}"

    def _refresh_from_cache(self, cached_instance):
        self._prefetched_objects_cache = {}
        non_loaded_fields = cached_instance.get_deferred_fields()
        for field in self._meta.concrete_fields:
            if field.attname in non_loaded_fields:
                # This field wasn't refreshed - skip ahead.
                continue
            setattr(self, field.attname, getattr(cached_instance, field.attname))
            # Clear cached foreign keys.
            if field.is_relation and field.is_cached(self):
                field.delete_cached_value(self)

        # Clear cached relations.
        for field in self._meta.related_objects:
            if field.is_cached(self):
                field.delete_cached_value(self)
        self.clear_caches()
        self.__refresh_time = time.time()

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self.clear_caches()
        self.__refresh_time = time.time()

    async def _set_cache_version(self):
        async with aredis(self._cachekey) as redis:
            await redis.eval(
                SETIFHIGHER,
                1,
                f"{self._cachekey}:version",
                self.version,
            )

        cache = caches["process"]
        cache.set(self._cachekey, self, timeout=600)
        self.__refresh_time = time.time()

    async def _set_cache_deleted(self):
        async with aredis(self._cachekey) as redis:
            await redis.set(
                f"{self._cachekey}:version",
                "deleted",
            )
