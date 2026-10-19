"""Austria appointment alerts. Python 3.11+, standard library only."""
import argparse
import base64
from datetime import datetime, timezone, date
from email.message import EmailMessage
import hashlib
import json
import os
from pathlib import Path
import smtplib
import ssl
import sys
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

CENTRES = {'London', 'Manchester', 'Edinburgh'}
STATE = Path('state/sent.json')

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Feed redirects are not accepted')

def open_feed(request):
    return build_opener(NoRedirect()).open(request, timeout=30)

def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError('Missing configuration: ' + name)
    return value

def candidates(feed, now=None):
    now = now or datetime.now(timezone.utc)
    if feed.get('country_from') != 'GBR' or feed.get('destination') != 'AUT' or feed.get('category') != 'tourist-schengen-c':
        raise ValueError('Feed does not match Austria tourist visas from the UK')
    checked = datetime.fromisoformat(feed['checked_at'].replace('Z', '+00:00'))
    if checked.tzinfo is None or not 0 <= (now - checked).total_seconds() <= 1800:
        raise ValueError('Feed timestamp must be timezone-aware and no more than 30 minutes old')
    result = []
    for slot in feed['slots']:
        when = datetime.fromisoformat(slot['starts_at'].replace('Z', '+00:00'))
        if when.tzinfo is None:
            raise ValueError('Slot timestamps must include a timezone')
        if (slot['centre'] in CENTRES and type(slot['capacity']) is int
                and slot['capacity'] >= 2 and when > now
                and when.date() < date(2026, 11, 14)):
            result.append(slot)
    return result

def load_feed():
    if required('LIVE_ENABLED') != 'true' or required('SOURCE_AUTHORISED') != 'true':
        raise ValueError('Live monitoring requires LIVE_ENABLED=true and SOURCE_AUTHORISED=true')
    required('SOURCE_PERMISSION_REFERENCE')
    url = required('FEED_URL')
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.username or parts.password:
        raise ValueError('Use an authorised HTTPS JSON feed without credentials in its URL')
    headers = {'Accept': 'application/json'}
    token = os.environ.get('FEED_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with open_feed(Request(url, headers=headers)) as response:
        if response.geturl() != url:
            raise ValueError('Configure the final feed URL; redirects are not accepted')
        data = response.read(1048577)
    if len(data) > 1048576:
        raise ValueError('Feed exceeds 1 MB')
    feed = json.loads(data)
    if feed.get('simulated') is not False:
        raise ValueError('Live feed must explicitly declare simulated=false')
    return feed

def send_email(message, subject='Austria visa alert notification', html=None):
    mail = EmailMessage()
    mail['Subject'] = subject
    mail['From'] = required('SMTP_USER')
    mail['To'] = required('EMAIL_TO')
    mail.set_content(message)
    if html is not None:
        mail.add_alternative(html, subtype='html')
    with smtplib.SMTP_SSL(os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
                          int(os.environ.get('SMTP_PORT', '465')), timeout=30,
                          context=ssl.create_default_context()) as smtp:
        smtp.login(required('SMTP_USER'), required('SMTP_PASSWORD'))
        refused = smtp.send_message(mail)
        if refused:
            raise RuntimeError('Email recipient rejected')

def send_whatsapp(message, test=False):
    sid = required('TWILIO_ACCOUNT_SID')
    if not sid.startswith('AC') or len(sid) != 34 or not sid.isalnum():
        raise ValueError('Invalid Twilio Account SID')
    fields = {'From': required('WHATSAPP_FROM'), 'To': required('WHATSAPP_TO')}
    content_sid = os.environ.get('TWILIO_CONTENT_SID', '').strip()
    if content_sid:
        fields['ContentSid'] = content_sid
        # The console's test template has no variables. Live alerts require
        # a separate approved template with one variable for the alert text.
        if not test:
            fields['ContentVariables'] = json.dumps({'1': message})
    elif test and os.environ.get('WHATSAPP_TEST_SESSION_OPEN') == 'true':
        fields['Body'] = message
    else:
        raise ValueError('WhatsApp requires an approved one-variable template; see README')
    auth = base64.b64encode((sid + ':' + required('TWILIO_AUTH_TOKEN')).encode()).decode()
    request = Request('https://api.twilio.com/2010-04-01/Accounts/' + sid + '/Messages.json',
                      data=urlencode(fields).encode(),
                      headers={'Authorization': 'Basic ' + auth})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not result.get('sid') or result.get('status') in {'failed', 'undelivered', 'canceled'}:
        raise RuntimeError('Twilio did not accept the message')

def notify_slots(slots, channels, state, save):
    failures = []
    for slot in slots:
        identity = json.dumps([slot['centre'], slot['starts_at']], separators=(',', ':'))
        key = hashlib.sha256(identity.encode()).hexdigest()
        message = ('Potential Austria tourist visa slot: ' + slot['centre'] + ', '
                   + slot['starts_at'] + ', capacity ' + str(slot['capacity'])
                   + '. For 2 applicants. Verify and book manually on VFS. Availability may change.')
        for channel in channels:
            receipt = key + ':' + channel
            if receipt in state:
                continue
            try:
                {'email': send_email, 'whatsapp': send_whatsapp}[channel](message)
                state[receipt] = datetime.now(timezone.utc).isoformat()
                save(state)
                print(channel + ': accepted by provider (delivery not yet confirmed)')
            except Exception:
                failures.append(channel)
                print(channel + ': failed; check configuration/provider console', file=sys.stderr)
    if failures:
        raise RuntimeError('Some notifications failed')

def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temp.replace(STATE)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['simulate', 'test-email', 'test-whatsapp', 'live'])
    args = parser.parse_args()
    if args.mode == 'simulate':
        feed = json.loads(Path('sample-feed.json').read_text(encoding='utf-8'))
        feed['checked_at'] = datetime.now(timezone.utc).isoformat()
        slots = candidates(feed)
        print('SIMULATION ONLY — no real availability checked; no messages sent.')
        print(json.dumps(slots, indent=2))
    elif args.mode == 'test-email':
        send_email('TEST ONLY: Your Austria alert email connection works. No appointment was detected.')
        print('Email accepted by SMTP server; check your inbox and spam folder.')
    elif args.mode == 'test-whatsapp':
        send_whatsapp('TEST ONLY: Austria alert connection test. No appointment was detected.', test=True)
        print('WhatsApp accepted by Twilio; check your phone and Twilio delivery logs.')
    else:
        slots = candidates(load_feed())
        channels = required('CHANNELS').split(',')
        if not channels or any(c not in {'email', 'whatsapp'} for c in channels):
            raise ValueError('CHANNELS must be email, whatsapp, or email,whatsapp')
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        notify_slots(slots, channels, state, save_state)
        print('Check complete: ' + str(len(slots)) + ' matching slots.')

if __name__ == '__main__':
    try:
        main()
    except HTTPError as error:
        # Numeric diagnostics only: provider bodies can contain personal data.
        provider_code = None
        try:
            body = json.loads(error.read(65536))
            if type(body.get('code')) is int:
                provider_code = body['code']
        except Exception:
            pass
        print('Provider request rejected: HTTP ' + str(error.code)
              + ', provider code ' + str(provider_code), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Never print exception bodies, which may contain credentials or feed URLs.
        print('Run failed (' + type(error).__name__ + '). Check README and provider logs.', file=sys.stderr)
        sys.exit(1)
