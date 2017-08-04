import asyncio
import functools
import json
import logging
import unittest
from unittest.mock import MagicMock

import aiohttp

import osrm

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

OSRM_HOST = 'http://127.0.0.1:5000'


class TestClient(unittest.TestCase):

    def setUp(self):
        self.client = osrm.Client(host=OSRM_HOST, timeout=1)
        self.mock_session = MagicMock()
        self.mock_client = osrm.Client(
            host=OSRM_HOST, session=self.mock_session)

    def test_server_error(self):
        self.mock_session.get.return_value = MagicMock(
            status_code=500,
            text='unexpected error')
        with self.assertRaises(osrm.OSRMServerException):
            response = self.mock_client.nearest(
                coordinates=[[-74.0056, 40.6197]],
                number=10
            )

    def test_nearest(self):
        response = self.client.nearest(
            coordinates=[[-74.00578245683002, 40.60600816104437]],
            radiuses=[70],
            number=20
        )
        assert response['code'] == 'Ok'
        assert len(response['waypoints']) == 12

        response = self.client.nearest(
            coordinates=[[-74.00578245683002, 40.60600816104437]],
            radiuses=[70],
            bearings=[[45,30]],
            number=20
        )
        assert response['code'] == 'Ok'
        assert len(response['waypoints']) == 3

        with self.assertRaises(AssertionError):
            self.client.nearest(
                coordinates=[[-200, 100]]
            )
        with self.assertRaises(AssertionError):
            self.client.nearest(
                coordinates=[[-74.00578245683002, 40.60600816104437]],
                bearings=[[720,360]],
            )

        with self.assertRaises(osrm.OSRMClientException) as cm:
            self.client.nearest(
                coordinates=[[-74.00578245683002, 40.60600816104437]],
                radiuses=[10],
                number=10
            )
        assert cm.exception.args[0]['code'] == 'NoSegment'

    def test_route(self):
        response = self.client.route(
            coordinates=[[-74.0056, 40.6197], [-74.0034, 40.6333]],
            overview=osrm.overview.full
        )
        assert response['code'] == 'Ok'

    def test_match(self):
        response = self.client.match(
            coordinates=[[-74.005482, 40.67922], [-74.005389, 40.679495], [-74.0050139317, 40.6797460083], [-74.004927, 40.679718], [-74.004694, 40.679651]],
            radiuses=[9, 9, 10, 3, 3],
            overview=osrm.overview.full
        )
        assert response['code'] == 'Ok'


def run_in_loop(f):
    @functools.wraps(f)
    def wrapper(testcase, *args, **kwargs):
        coro = asyncio.coroutine(f)
        future = asyncio.wait_for(coro(testcase, *args, **kwargs), timeout=15)
        return testcase.loop.run_until_complete(future)
    return wrapper


class TestAioHTTPClient(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _setUp():
            self.session = aiohttp.ClientSession(loop=self.loop)
            self.client = osrm.AioHTTPClient(
                host=OSRM_HOST, session=self.session, timeout=0.2
            )

        self.mock_session = MagicMock()
        self.mock_client = osrm.AioHTTPClient(
            host=OSRM_HOST, session=self.mock_session,
            timeout=0.2, max_retries=3
        )

        self.loop.run_until_complete(_setUp())


    def tearDown(self):
        self.loop.run_until_complete(self.session.close())
        self.loop.close()

    @run_in_loop
    async def test_nearest(self):
        response = await self.client.nearest(
            coordinates=[[-74.0056, 40.6197]],
            number=10
        )
        assert response['code'] == 'Ok'

    @run_in_loop
    async def test_match(self):
        response = await self.client.match(
            coordinates=[[-74.005482, 40.67922], [-74.005389, 40.679495], [-74.0050139317, 40.6797460083], [-74.004927, 40.679718], [-74.004694, 40.679651]],
            radiuses=[9, 9, 10, 3, 3],
            overview=osrm.overview.full,
            tidy=False,
            gaps=osrm.gaps.split
        )
        assert response['code'] == 'Ok'


    @run_in_loop
    async def test_route(self):
        response = await self.client.route(
            coordinates=[[-74.0056, 40.6197], [-74.0034, 40.6333]],
            overview=osrm.overview.full
        )
        assert response['code'] == 'Ok'

    @run_in_loop
    async def test_retry(self):
        counter = 0
        def mock_get(url, **kwargs):
            nonlocal counter
            if counter < 2:
                counter += 1
                raise asyncio.TimeoutError('timeout')
            return aiohttp.client._RequestContextManager(
                asyncio.coroutine(
                    lambda: MagicMock(
                        status=200,
                        url=url,
                        text=asyncio.coroutine(lambda: '{}')
                    )
                )()
            )

        self.mock_session.get = mock_get

        response = await self.mock_client.nearest(
            coordinates=[[-74.0056, 40.6197]], number=10
        )
        assert counter == 2

    @run_in_loop
    async def test_exceeded_max_retry(self):
        counter = 0
        def mock_get(url, **kwargs):
            nonlocal counter
            counter += 1
            raise asyncio.TimeoutError('timeout')

        self.mock_session.get = mock_get
        with self.assertRaises(osrm.OSRMServerException) as cm:
            response = await self.mock_client.nearest(
                coordinates=[[-74.0056, 40.6197]], number=10
            )
        assert cm.exception.args[1] == 'server timeout'
        assert counter == self.mock_client.max_retries

    @run_in_loop
    async def test_real_timeout(self):
        client = osrm.AioHTTPClient(
            host=OSRM_HOST, timeout=0.01, max_retries=1)
        with self.assertRaises(osrm.OSRMServerException) as cm:
            await client.match(
                coordinates=[[-73.999, 40.724], [-73.994, 40.728]],
                radiuses=[150, 150]
            )
            await client.close()

        assert cm.exception.args[1] == 'server timeout'
