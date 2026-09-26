"""Private browser-session metadata, never an IP address or raw user agent."""
import math
import re
import secrets

BROWSERS = {'Unknown', 'Onion Browser', 'Edge', 'Opera', 'Samsung Internet', 'Firefox', 'Chrome', 'Safari'}
PLATFORMS = {'Unknown', 'iOS', 'Android', 'Windows', 'macOS', 'Linux', 'ChromeOS'}


def client_labels(user_agent):
    agent = user_agent[:512].lower()
    browser = next((label for needle, label in (
        ('onionbrowser', 'Onion Browser'), ('onion browser', 'Onion Browser'),
        ('edg', 'Edge'), ('opr/', 'Opera'), ('samsungbrowser/', 'Samsung Internet'),
        ('firefox/', 'Firefox'), ('fxios/', 'Firefox'), ('chrome/', 'Chrome'),
        ('crios/', 'Chrome'), ('safari/', 'Safari'),
    ) if needle in agent), 'Unknown')
    platform = next((label for needle, label in (
        ('iphone', 'iOS'), ('ipad', 'iOS'), ('ipod', 'iOS'), ('android', 'Android'),
        ('cros', 'ChromeOS'), ('windows', 'Windows'), ('macintosh', 'macOS'), ('linux', 'Linux'),
    ) if needle in agent), 'Unknown')
    return {'browser': browser, 'platform': platform}


def metadata(now, user_agent):
    return {'id': secrets.token_hex(16), 'created': now, 'last_seen': now, **client_labels(user_agent)}


def valid_metadata(value, now):
    return (isinstance(value.get('id'), str) and re.fullmatch('[0-9a-f]{32}', value['id']) is not None
            and value.get('browser') in BROWSERS and value.get('platform') in PLATFORMS
            and (value.get('created') is None or type(value['created']) in (int,float)
                 and math.isfinite(value['created']) and 0<=value['created']<=now+300)
            and type(value.get('last_seen')) in (int,float) and math.isfinite(value['last_seen'])
            and 0<=value['last_seen']<=now+300)
