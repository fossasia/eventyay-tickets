import copy
import logging
import os
import pickle
import random
import time

from channels.db import database_sync_to_async
from django.core.cache import caches
from django.db import models, transaction

from eventyay.core.utils.redis import aredis, sredis

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
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            update_fields = kwargs["update_fields"]
            if "version" not in update_fields:
                if isinstance(update_fields, set):
                    update_fields.add("version")
                elif isinstance(update_fields, list):
                    update_fields.append("version")
                else:
                    kwargs["update_fields"] = list(update_fields) + ["version"]
        self.version += 1
        r = super().save(*args, **kwargs)
        transaction.on_commit(self._set_cache_version_sync)
        return r

    def delete(self, *args, **kwargs):
        r = super().delete(*args, **kwargs)
        transaction.on_commit(self._set_cache_deleted_sync)
        return r

    def touch(self):
        self.save(update_fields=["version"])
        self.clear_caches()

    def __getstate__(self):
        # Process-cache only needs concrete fields. Related objects (e.g. Room.event
        # with Hierarkey settings) can embed callables that Twisted fails to unpickle.
        state = super().__getstate__()
        state["_state"] = copy.copy(state["_state"])
        state["_state"].fields_cache = {}
        state.pop("_prefetched_objects_cache", None)
        return state

    async def refresh_from_db_if_outdated(self, allowed_age=0):
        if allowed_age:
            # In some places, we allow the cache to be a little outdated to avoid thousands
            # of GET calls to redis. We add some random variance to the duration to soften
            # load spikes if all threads force-refreshed at the same time. We also do not do
            # this during unit testing, which is bad (since it means tests are different from
            # the real event) but also necessary if we don't want to have long sleep() calls
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

        cache = caches["process"] if "process" in caches.settings else caches["default"]
        try:
            cached_instance = cache.get(self._cachekey)
        except (
            AttributeError,
            TypeError,
            ValueError,
            EOFError,
            ImportError,
            IndexError,
            pickle.UnpicklingError,
        ):
            logger.warning(
                "VersionedModel.refresh_from_db_if_outdated: dropping unreadable cache for %s",
                self._cachekey,
            )
            cache.delete(self._cachekey)
            cached_instance = None

        if cached_instance is not None and getattr(cached_instance, "version", None) == latest_version:
            self._refresh_from_cache(cached_instance)
            return

        await database_sync_to_async(self.refresh_from_db)()
        try:
            cache.set(self._cachekey, self, timeout=600)
        except (TypeError, AttributeError):
            logger.debug(
                "VersionedModel.refresh_from_db_if_outdated: skipping unpicklable %s pk=%s",
                self.__class__.__name__,
                self.pk,
            )
        if latest_version < self.version:
            await self._set_cache_version_async()

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
        from django_scopes import scopes_disabled
        with scopes_disabled():
            super().refresh_from_db(*args, **kwargs)
        self.clear_caches()
        self.__refresh_time = time.time()

    def _set_cache_version_sync(self):
        with sredis(self._cachekey) as redis_conn:
            redis_conn.eval(
                SETIFHIGHER,
                1,
                f"{self._cachekey}:version",
                self.version,
            )

        self._cache_post_update()

    async def _set_cache_version_async(self):
        async with aredis(self._cachekey) as redis:
            await redis.eval(
                SETIFHIGHER,
                1,
                f"{self._cachekey}:version",
                self.version,
            )

        self._cache_post_update()

    def _cache_post_update(self):
        cache = caches["process"] if "process" in caches.settings else caches["default"]
        try:
            cache.set(self._cachekey, self, timeout=600)
        except (TypeError, AttributeError):
            logger.debug(
                "VersionedModel._cache_post_update: skipping unpicklable %s pk=%s",
                self.__class__.__name__,
                self.pk,
            )
        self.__refresh_time = time.time()

    def _set_cache_deleted_sync(self):
        with sredis(self._cachekey) as redis_conn:
            redis_conn.set(
                f"{self._cachekey}:version",
                "deleted",
            )

    async def _set_cache_deleted_async(self):
        async with aredis(self._cachekey) as redis:
            await redis.set(
                f"{self._cachekey}:version",
                "deleted",
            )
