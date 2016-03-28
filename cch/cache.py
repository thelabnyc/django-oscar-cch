from django.core.cache import caches
import time

from . import settings


cache = caches[settings.CCH_CACHE_BACKEND]


def _basket_uat_cache_key(basket):
    return '%s_basket_uat_%s' % (__name__, basket.id)


def get_basket_uat(basket):
    key = _basket_uat_cache_key(basket)
    uat = cache.get(key)
    if not uat:
        uat = update_basket_uat(basket)
    return uat


def update_basket_uat(basket):
    uat = time.time()
    key = _basket_uat_cache_key(basket)
    cache.set(key, uat, settings.CCH_BASKET_UAT_CACHE_SECONDS)
    return uat
