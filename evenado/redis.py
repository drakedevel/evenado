from tornado import gen
from tornado.concurrent import return_future
from tornadoredis.client import Client as RedisClient


class RedisCacheProvider(object):
    def __init__(self, *args, **kwargs):
        self._redis = RedisClient(*args, **kwargs)

    @staticmethod
    def _realkey(silo, key):
        return 'evenado/cache/%s/%s' % (silo, key)

    @return_future
    def get(self, silo, key, callback):
        self._redis.get(self._realkey(silo, key), callback=callback)

    @gen.coroutine
    def purge(self, silo):
        keys = yield gen.Task(self._redis.keys, self._realkey(silo, '*'))
        yield gen.Task(self._redis.delete, *keys)

    @return_future
    def set(self, silo, key, value, ttl, callback):
        self._redis.execute_command('SET', self._realkey(silo, key), value,
                                    'EX', ttl, callback=callback)
