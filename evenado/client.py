from functools import wraps
from tornado import gen

from .rawclient import RawAPIClient, parse_date

DEFAULT_ENDPOINT = 'https://api.eveonline.com'


def _parse_object(xml, name, class_):
    return class_(xml.find('.//%s' % name))


def _parse_rowset(xml, name, class_):
    return [class_(e) for e in
            xml.findall(".//rowset[@name='%s']/row" % name)]


class APIError(Exception):
    def __init__(self, et):
        self.code = int(et.attrib.get('code'))
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
        self.date = parse_date(et.attrib.get('eventDate'))
        self.title = et.attrib.get('eventTitle')
        self.text = et.attrib.get('eventText')

    def __repr__(self):
        return "<CalendarEvent '%s'>" % self.title


class Character(object):
    def __init__(self, et):
        self.id = int(et.attrib.get('characterID'))
        self.name = et.attrib.get('name') or et.attrib.get('characterName')
        self.corporation_id = int(et.attrib.get('corporationID'))
        self.corporation_name = et.attrib.get('corporationName')

    def __repr__(self):
        return "<Character %d '%s'>" % (self.id, self.name)


class KeyInfo(object):
    def __init__(self, et):
        self.access_mask = int(et.attrib.get('accessMask'))
        self.type = et.attrib.get('type')
        if et.attrib.get('expires'):
            self.expires = parse_date(et.attrib.get('expires'))
        else:
            self.expires = None
        self.characters = _parse_rowset(et, 'characters', Character)

    def __repr__(self):
        return "<KeyInfo %s mask=%s expires=%s characters=%r>" % (
            self.type, self.access_mask, self.expires, self.characters)


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

    @_apicall('char/UpcomingCalendarEvents', ['characterID'])
    def upcoming_calendar_events(self, xml):
        return _parse_rowset(xml, 'upcomingEvents', CalendarEvent)
