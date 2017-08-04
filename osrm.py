import asyncio
import collections
import enum
import logging
import numbers
import random

try:
    import ujson as json
except ImportError:
    import json


from urllib.parse import urlencode

logger = logging.getLogger(__name__)

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import requests
except ImportError:
    requests = None

if not (aiohttp or requests):
    logger.error('Could not import none of modules \'aiohttp\' or \'requests\'')


class overview(enum.Enum):
    simplified = 'simplified'
    full = 'full'
    false = 'false'


# alias for avoiding name collision
osrm_overview = overview


class geometries(enum.Enum):
    polyline = 'polyline'
    polyline6 = 'polyline6'
    geojson = 'geojson'


# alias for avoiding name collision
osrm_geometries = geometries


class gaps(enum.Enum):
    split = 'split'
    ignore = 'ignore'


# alias for avoiding name collision
osrm_gaps = gaps


class OSRMException(Exception):
    pass


class OSRMServerException(OSRMException):
    pass


class OSRMClientException(OSRMException):
    pass


def _check_pairs(items):
    ''' checking that 'items' has format [[Number, Number], ...]'''
    return (
        isinstance(items, collections.Iterable) and
        all([isinstance(p, collections.Iterable) for p in items]) and
        all([
            isinstance(p[0], numbers.Number) and
            isinstance(p[1], numbers.Number) and
            len(p) == 2
            for p in items]))


class BaseRequest:

    def __init__(self, coordinates, radiuses=[], bearings=[], hints=[]):
        assert _check_pairs(coordinates), \
            '''coordinates must be in format [[longitude, latitude],...]'''
        assert all([
            -180 <= lon <= 180 and -90 <= lat <= 90
            for lon, lat in coordinates]), \
            ''''longitude' should be -180..180 and 'latitude' should be -90..90 (actual: {})'''.format(coordinates)
        assert _check_pairs(bearings), \
            '''bearings must be in format [[value, range],...]'''
        assert all([
            0 <= bvalue <= 360 and 0 <= brange <= 180
            for bvalue, brange in bearings]), \
            '''bearing 'value' should be 0..360 and 'range' should be 0..180 (actual: {})'''.format(bearings)
        assert isinstance(radiuses, list)
        assert isinstance(bearings, list)
        assert isinstance(hints, list)

        self.coordinates = coordinates
        self.radiuses = radiuses
        self.bearings = bearings
        self.hints = hints

    def get_coordinates(self):
        return self._encode_pairs(self.coordinates)

    def get_options(self):
        return {
            'radiuses': self._encode_array(self.radiuses),
            'bearings': self._encode_pairs(self.bearings),
            'hints': self._encode_array(self.hints)
        }

    def _encode_array(self, value):
        return ';'.join(map(lambda x: str(x) if x else "", value))

    def _encode_bool(self, value):
        return 'true' if value else 'false'

    def _encode_pairs(self, coordinates):
        return ';'.join([','.join(map(str, coord)) for coord in coordinates])

    def decode_response(self, url, status, response):
        if status == 200:
            return json.loads(response)
        elif status == 400:
            raise OSRMClientException(json.loads(response))
        raise OSRMServerException(url, response)


class NearestRequest(BaseRequest):

    service = 'nearest'

    def __init__(self, number=1, **kwargs):
        super().__init__(**kwargs)
        self.number = number

    def get_options(self):
        options = super().get_options()
        options['number'] = self.number
        return options


class RouteRequest(BaseRequest):

    service = 'route'

    def __init__(
            self,
            alternatives=False,
            steps=False, annotations=False,
            geometries=geometries.geojson,
            overview=overview.simplified, **kwargs):
        super().__init__(**kwargs)

        assert isinstance(alternatives, bool)
        assert isinstance(steps, bool)
        assert isinstance(annotations, bool)
        assert isinstance(geometries, osrm_geometries)
        assert isinstance(overview, osrm_overview)

        self.alternatives = alternatives
        self.steps = steps
        self.annotations = annotations
        self.geometries = geometries
        self.overview = overview

    def get_options(self):
        options = super().get_options()
        options.update({
            'alternatives': self._encode_bool(self.alternatives),
            'steps':        self._encode_bool(self.steps),
            'annotations':  self._encode_bool(self.annotations),
            'geometries':   self.geometries.value,
            'overview':     self.overview.value
        })
        return options


class MatchRequest(RouteRequest):

    service = 'match'

    def __init__(
            self,
            timestamps=[],
            gaps=gaps.split,
            tidy=False,
            **kwargs):
        super().__init__(**kwargs)
        assert isinstance(timestamps, list)
        assert isinstance(gaps, osrm_gaps)
        assert isinstance(tidy, bool)

        self.timestamps = timestamps
        self.gaps = gaps
        self.tidy = tidy

    def get_options(self):
        options = super().get_options()
        options.pop('alternatives', None)
        options['timestamps'] = self._encode_array(self.timestamps)

        # Don't send default values (for compatibility with 5.6)
        if self.gaps.value == osrm_gaps.split:
            options['gaps'] = self.gaps.value
        if self.tidy:
            options['tidy'] = self._encode_bool(self.tidy)
        return options


class BaseClient:

    def __init__(
            self,
            host='http://localhost:5000',
            version='v1', profile='driving',
            timeout=5, max_retries=5):
        assert isinstance(host, str)
        assert isinstance(version, str)
        assert isinstance(profile, str)
        assert isinstance(timeout, numbers.Number)
        assert isinstance(max_retries, int) and max_retries >= 1

        self.host = host
        self.version = version
        self.profile = profile
        self.timeout = timeout
        self.max_retries = max_retries

    def _build_request(self, request):
        url = '{host}/{service}/{version}/{profile}/{coordinates}'.format(
            host=self.host,
            service=request.service,
            version=self.version,
            profile=self.profile,
            coordinates=request.get_coordinates())
        params = {
            k: v
            for k, v in request.get_options().items()
            if v
        }
        logger.debug('request url=%s; params=%s', url, params)
        return (url, params)


class Client(BaseClient):

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not requests:
            raise RuntimeError('Module \'requests\' is not available')
        self.session = session or requests.Session()
        self.a = requests.adapters.HTTPAdapter(max_retries=self.max_retries)
        self.session.mount('http://', self.a)

    def nearest(self, **kwargs):
        return self._request(
            NearestRequest(**kwargs)
        )

    def route(self, **kwargs):
        return self._request(
            RouteRequest(**kwargs)
        )

    def match(self, **kwargs):
        return self._request(
            MatchRequest(**kwargs)
        )

    def _request(self, request):
        if not requests:
            raise RuntimeError('Module \'requests\' is not available')
        url, params = self._build_request(request)
        response = self.session.get(url, params=params, timeout=self.timeout)
        return request.decode_response(url, response.status_code, response.text)


class AioHTTPClient(BaseClient):

    BACKOFF_MAX = 120
    BACKOFF_FACTOR = 0.5

    def __init__(self, *args, session=None, loop=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not aiohttp:
            raise RuntimeError('Module \'aiohttp\' is not available')
        if not session:
            self.loop = loop or asyncio.get_event_loop()
            self.session = aiohttp.ClientSession(loop=self.loop)
        else:
            self.session = session

    async def nearest(self, **kwargs):
        return await self._request(
            NearestRequest(**kwargs)
        )

    async def route(self, **kwargs):
        return await self._request(
            RouteRequest(**kwargs)
        )

    async def match(self, **kwargs):
        return await self._request(
            MatchRequest(**kwargs)
        )

    def exp_backoff(self, attempt):
        timeout = min(self.timeout * (2 ** attempt), self.BACKOFF_MAX)
        return timeout + random.uniform(0, self.BACKOFF_FACTOR * timeout)

    async def _request(self, request):
        url, params = self._build_request(request)
        attempt = 0
        while attempt < self.max_retries:
            try:
                # This is a workaround for the https://github.com/aio-libs/aiohttp/issues/1901
                request_url = "{}?{}".format(url, urlencode(params))
                async with self.session.get(
                        request_url, timeout=self.timeout) as response:
                    body = await response.text()
                    return request.decode_response(
                        response.url, response.status, body)
            except asyncio.TimeoutError:
                timeout = self.exp_backoff(attempt)
                logger.info(
                    'Timeout error url=%s (remaining tries %s, sleeping %.2f secs)',
                    url, self.max_retries - attempt, timeout)
                await asyncio.sleep(timeout)
                attempt += 1

        raise OSRMServerException(url, 'server timeout')

    async def close(self):
        await self.session.close()
