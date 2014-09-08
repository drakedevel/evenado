from datetime import datetime
from functools import wraps
from tornado import gen

from .rawclient import RawAPIClient, parse_date

DEFAULT_ENDPOINT = 'https://api.eveonline.com'


def _parse_object(xml, name, class_):
    return class_(xml.find('.//%s' % name))


def _parse_rowset(xml, name, class_):
    return [class_(e) for e in
            xml.findall(".//rowset[@name='%s']/row" % name)]


def _a(et, attr, type_=None):
    if type_ is None:
        return et.attrib.get(attr)
    elif type_ is bool:
        return bool(_a(et, attr, int))
    elif type_ is datetime:
        return parse_date(_a(et, attr, str))
    else:
        return type_(et.attrib.get(attr))


class APIError(Exception):
    def __init__(self, et):
        self.code = _a(et, 'code', int)
        self.message = et.text

    def __repr__(self):
        return "<APIError %d '%s'>" % (self.code, self.message)

    def __str__(self):
        return "API Error %d: %s" % (self.code, self.message)


class AccountStatus(object):
    def __init__(self, et):
        self.paid_until = parse_date(et.find('paidUntil').text)
        self.create_date = parse_date(et.find('createDate').text)
        self.logon_count = int(et.find('logonCount').text)
        self.logon_minutes = int(et.find('logonMinutes').text)

    def __repr__(self):
        return "<AccountStatus ...>"


class CalendarEvent(object):
    def __init__(self, et):
        self.date = _a(et, 'eventDate', datetime)
        self.title = _a(et, 'eventTitle')
        self.text = _a(et, 'eventText')

    def __repr__(self):
        return "<CalendarEvent '%s'>" % self.title


class Character(object):
    def __init__(self, et):
        self.id = _a(et, 'characterID', int)
        self.name = _a(et, 'name') or _a(et, 'characterName')
        self.corporation_id = _a(et, 'corporationID', int)
        self.corporation_name = _a(et, 'corporationName')

    def __repr__(self):
        return "<Character %d '%s'>" % (self.id, self.name)


class KeyInfo(object):
    def __init__(self, et):
        self.access_mask = _a(et, 'accessMask', int)
        self.type = _a(et, 'type')
        if et.attrib.get('expires'):
            self.expires = _a(et, 'expires', datetime)
        else:
            self.expires = None
        self.characters = _parse_rowset(et, 'characters', Character)

    def __repr__(self):
        return "<KeyInfo %s mask=%s expires=%s characters=%r>" % (
            self.type, self.access_mask, self.expires, self.characters)


class MarketOrder(object):
    STATE_ACTIVE = 0
    STATE_CLOSED = 1
    STATE_EXPIRED = 2
    STATE_CANCELLED = 3
    STATE_PENDING = 4
    STATE_CHAR_DELETED = 5

    def __init__(self, et):
        self.id = _a(et, 'orderID', int)
        self.character_id = _a(et, 'charID', int)
        self.station_id = _a(et, 'stationID', int)
        self.volume_entered = _a(et, 'volEntered', int)
        self.volume_remaining = _a(et, 'volRemaining', int)
        self.min_volume = _a(et, 'minVolume', int)
        self.state = _a(et, 'orderState', int)
        self.type_id = _a(et, 'typeID', int)
        self.range = _a(et, 'range', int)
        self.account_key = _a(et, 'accountKey', int)
        self.duration = _a(et, 'duration', int)
        self.escrow = _a(et, 'escrow', float)
        self.price = _a(et, 'price', float)
        self.bid = _a(et, 'bid', bool)
        self.issued = _a(et, 'issued', datetime)


class Transaction(object):
    def __init__(self, et):
        self.id = _a(et, 'transactionID', int)
        self.date = _a(et, 'transactionDateTime', datetime)
        self.quantity = _a(et, 'quantity', int)
        self.type_name = _a(et, 'typeName')
        self.type_id = _a(et, 'typeID', int)
        self.price = _a(et, 'price', float)
        self.client_id = _a(et, 'clientID', int)
        self.client_name = _a(et, 'clientName')
        self.station_id = _a(et, 'stationID', int)
        self.station_name = _a(et, 'stationName')
        self.transaction_type = _a(et, 'transactionType')
        self.transaction_for = _a(et, 'transactionFor')
        self.journal_transaction_id = _a(et, 'journalTransactionID', int)


class APIClient(object):
    def __init__(self, cache, keyid=None, vcode=None,
                 endpoint=DEFAULT_ENDPOINT):
        self._raw = RawAPIClient(cache, endpoint, keyid, vcode)

    def _apicall(name, args=[]):
        def deco(f):
            @wraps(f)
            @gen.coroutine
            def wrapper(self, **kwargs):
                # Validate arguments and handle any objects with "id" attrs
                for k in kwargs:
                    if k not in args:
                        raise TypeError("Got unexpected kwarg %s" % k)
                    if hasattr(kwargs[k], 'id'):
                        kwargs[k] = kwargs[k].id

                # Perform the API request and do error handling
                raw_result = yield self._raw.perform(name, **kwargs)
                err_et = raw_result.find('error')
                if err_et is not None:
                    raise APIError(err_et)

                result = f(self, raw_result)
                raise gen.Return(result)
            return wrapper
        return deco

    @_apicall('account/AccountStatus')
    def account_status(self, xml):
        return _parse_object(xml, 'result', AccountStatus)

    @_apicall('account/APIKeyInfo')
    def api_key_info(self, xml):
        return _parse_object(xml, 'key', KeyInfo)

    @_apicall('account/Characters')
    def characters(self, xml):
        return _parse_rowset(xml, 'characters', Character)

    @_apicall('char/MarketOrders', ['characterID'])
    def market_orders(self, xml):
        return _parse_rowset(xml, 'orders', MarketOrder)

    @_apicall('char/UpcomingCalendarEvents', ['characterID'])
    def upcoming_calendar_events(self, xml):
        return _parse_rowset(xml, 'upcomingEvents', CalendarEvent)

    @_apicall('char/WalletTransactions', ['characterID', 'fromID', 'rowCount'])
    def wallet_transactions(self, xml):
        return _parse_rowset(xml, 'transactions', Transaction)
