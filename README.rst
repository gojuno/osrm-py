osrm-py
=======

A Python client for `OSRM API`_

.. _`OSRM API`: https://github.com/Project-OSRM/osrm-backend/wiki/Server-api

Running the test suite
----------------------

.. code-block:: python

    python setup.py test


Requires
--------

* requests
* aiohttp

Usage
-----

With using `requests`

.. code-block:: python

    import osrm

    client = osrm.Client(host='http://localhost:5000')

    response = client.route(
        coordinates=[[-74.0056, 40.6197], [-74.0034, 40.6333]],
        overview=osrm.overview.full)

    print(response)

With using `aiohttp`

.. code-block:: python

    import asyncio
    import osrm

    loop = asyncio.get_event_loop()

    async def request():
        client = osrm.AioHTTPClient(host='http://localhost:5000')
        response = await client.route(
            coordinates=[[-74.0056, 40.6197], [-74.0034, 40.6333]],
            overview=osrm.overview.full)
        print(response)
        await client.close()

    loop.run_until_complete(request())
