import hashlib
import logging
import xml.etree.cElementTree as ET
from datetime import datetime
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPError, HTTPRequest
from urllib import urlencode

logger = logging.getLogger('evenado.client')


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')


class RawAPIClient(object):
    def __init__(self, cache, endpoint, keyid, vcode):
        self._cache = cache
        self._endpoint = endpoint
        self._keyid = keyid
        self._vcode = vcode

        self._http = AsyncHTTPClient()

    @gen.coroutine
    def perform(self, action, **kwargs):
        # Construct a (authenticated) URL for the request
        if self._keyid is not None:
            kwargs.update(keyID=self._keyid, vCode=self._vcode)
        query = urlencode(sorted(kwargs.items()))
        url = '%s/%s.xml.aspx?%s' % (self._endpoint, action, query)

        # Construct a sanitized URL for caching and logging purposes
        if 'vCode' in kwargs:
            kwargs['vCode'] = 'SANITIZED'
        query = urlencode(sorted(kwargs.items()))
        sanitized_url = '%s/%s.xml.aspx?%s' % (self._endpoint, action, query)

        # Check the cache
        silo = self._keyid or 'public'
        cache_key = hashlib.sha256(sanitized_url).hexdigest()
        cache_value = yield self._cache.get(silo, cache_key)
        if cache_value is not None:
            logger.debug("Cache hit on %s (key = %s)", sanitized_url,
                         cache_key)
            raise gen.Return(ET.fromstring(cache_value))
        logger.debug("Cache miss on %s (key = %s)", sanitized_url, cache_key)

        # Cache miss -- perform the request
        request = HTTPRequest(url, user_agent='evenado/0.0.1')
        try:
            response = yield self._http.fetch(request)
        except HTTPError as e:
            # EVE API returns a useful XML blob including cache info on errors
            if hasattr(e, 'response'):
                response = e.response
            else:
                raise
        value = ET.fromstring(response.body)

        # Get caching requirements and cache if required
        cur_time = parse_date(value.find('currentTime').text)
        exp_time = parse_date(value.find('cachedUntil').text)
        if exp_time > cur_time:
            expire = exp_time - cur_time
            logger.debug("Caching for %s requested for %s (key = %s)",
                         expire, sanitized_url, cache_key)
            yield self._cache.set(silo, cache_key, response.body,
                                  int(expire.total_seconds()))

        raise gen.Return(value)
