import logging
from urllib.parse import quote

import requests
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.views.generic.base import View

from eventyay.base.settings import GlobalSettingsObject


logger = logging.getLogger(__name__)


class GeoCodeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        q = self.request.GET.get('q')
        cd = cache.get(f'geocode:{q}')
        if cd:
            return JsonResponse({'success': True, 'results': cd}, status=200)

        gs = GlobalSettingsObject()
        try:
            if gs.settings.opencagedata_apikey:
                res = self._use_opencage(q)
            elif gs.settings.mapquest_apikey:
                res = self._use_mapquest(q)
            else:
                return JsonResponse({'success': False, 'results': []}, status=200)
        except OSError:
            logger.exception('Geocoding failed')
            return JsonResponse({'success': False, 'results': []}, status=200)

        cache.set(f'geocode:{q}', res, timeout=3600 * 6)
        return JsonResponse({'success': True, 'results': res}, status=200)

    def _use_opencage(self, q):
        gs = GlobalSettingsObject()

        r = requests.get(
            f'https://api.opencagedata.com/geocode/v1/json?q={quote(q)}&key={gs.settings.opencagedata_apikey}'
        )
        r.raise_for_status()
        d = r.json()
        res = [
            {
                'formatted': r['formatted'],
                'lat': r['geometry']['lat'],
                'lon': r['geometry']['lng'],
            }
            for r in d['results']
        ]
        return res

    def _use_mapquest(self, q):
        gs = GlobalSettingsObject()

        r = requests.get(
            f'https://www.mapquestapi.com/geocoding/v1/address?location={quote(q)}&key={gs.settings.mapquest_apikey}'
        )
        r.raise_for_status()
        d = r.json()
        res = [
            {
                'formatted': q,
                'lat': r['locations'][0]['latLng']['lat'],
                'lon': r['locations'][0]['latLng']['lng'],
            }
            for r in d['results']
        ]
        return res
