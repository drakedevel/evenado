Warning
-------

This is an early prototype. There aren't any known bugs, but there are very few supported API calls at this point. Stay tuned or submit a pull request!

Overview
--------

EVEnado is an asynchronous EVE API library. It automatically caches all API responses (including error responses) for the minimum allowed time. The cache system is pluggable, and EVEnado comes with a Redis implementation.

One thing to note is that for some API calls, caching is *mandatory*. As in, the request will fail if you re-request before the expiration time, which may be up to 24 hours. As a result, memcache-style data stores are not suitable for use as a cache plugin.

Usage
-----

Usage is straightforward and best explained by example:

```python
from evenado.client import APIClient
from evenado.redis import RedisCacheProvider
from tornado import gen, ioloop

@gen.coroutine
def async_main():
    client = APIClient(RedisCacheProvider(), keyid=..., vcode=...)
    for char in (yield client.characters()):
        print char.name

if __name__ == '__main__':
    ioloop.IOLoop.instance().run_sync(async_main)
```

Of course you can also use the library within the context of a Tornado HTTPServer or anything else which can use Tornado coroutines.
