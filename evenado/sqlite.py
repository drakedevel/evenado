import os
import sqlite3
from tornado.concurrent import return_future


class SqliteCacheProvider(object):
    def __init__(self, path=None):
        if path is None:
            path = os.path.expanduser('~/.cache/evenado/cache.db')
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
        self._sqlite = sqlite3.connect(path)
        self._sqlite.execute('CREATE TABLE IF NOT EXISTS cache('
                             'silo TEXT, key TEXT, value TEXT, expires TEXT,'
                             'PRIMARY KEY(silo, key))')
        self._sqlite.execute('DELETE FROM cache'
                             '  WHERE datetime(expires) <= datetime("now")')
        self._sqlite.commit()

    @return_future
    def get(self, silo, key, callback):
        cursor = self._sqlite.cursor()
        try:
            cursor.execute('SELECT value FROM cache'
                           '  WHERE silo=? AND key=?'
                           '  AND datetime(expires) > datetime("now")',
                           (silo, key))
            row = cursor.fetchone()
        finally:
            cursor.close()
        callback(row[0] if row else None)

    @return_future
    def purge(self, silo, callback):
        self._sqlite.execute('DELETE FROM cache WHERE silo=?', silo)
        self._sqlite.commit()
        callback()

    @return_future
    def set(self, silo, key, value, ttl, callback):
        query = ('INSERT OR REPLACE INTO'
                 '  cache(silo, key, value, expires)'
                 '  VALUES (?, ?, ?, datetime('
                 '    strftime("%s", "now") + ?, "unixepoch"))')
        self._sqlite.execute(query, (silo, key, value, ttl))
        self._sqlite.commit()
        callback()
