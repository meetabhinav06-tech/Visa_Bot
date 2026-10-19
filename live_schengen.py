"""Third-party availability leads for one applicant, not confirmed bookings."""
from datetime import datetime, timezone, date
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import os
from html import escape
from bot import send_email, send_whatsapp, required
from probe_parse import URL
from telegram_alert import notify_leads, send_telegram

COUNTRIES = {'AT':'Austria','BE':'Belgium','BG':'Bulgaria','HR':'Croatia',
 'CZ':'Czechia','DK':'Denmark','EE':'Estonia','FI':'Finland','FR':'France',
 'DE':'Germany','GR':'Greece','HU':'Hungary','IS':'Iceland','IT':'Italy',
 'LV':'Latvia','LI':'Liechtenstein','LT':'Lithuania','LU':'Luxembourg',
 'MT':'Malta','NL':'Netherlands','NO':'Norway','PL':'Poland','PT':'Portugal',
 'RO':'Romania','SK':'Slovakia','SI':'Slovenia','ES':'Spain','SE':'Sweden',
 'CH':'Switzerland'}
STATE = Path('schengen-state/sent.json')

def send_check_status(rows, fresh, checked):
    from zoneinfo import ZoneInfo
    uk_checked = datetime.fromisoformat(checked).astimezone(ZoneInfo('Europe/London')).strftime('%d %B %Y, %H:%M UK time')
    heading = 'AUSTRIA: AVAILABILITY LEAD FOUND' if rows else 'AUSTRIA: NO MATCHING LEADS FOUND'
    blocks = [heading]
    for row in rows:
        readable = date.fromisoformat(row['date']).strftime('%d %B %Y')
        blocks.append('Location: ' + row['centre'] + '\nAppointment date: ' + readable)
    if not rows:
        blocks.append('Location / date: none returned by the feed.')
    blocks += ['Applicants: 1 | Visa: Tourist',
               'Centres checked: London, Manchester, Edinburgh',
               'Appointment date filter: before 14 November 2026',
               'New leads this check: ' + str(len(fresh)),
               'Last checked: ' + uk_checked,
               'Checks scheduled every 2 hours; GitHub may delay runs.',
               'VERIFY BEFORE BOOKING: Third-party reported information. Availability and capacity are not confirmed by the official booking portal. No booking made.']
    message = '\n\n'.join(blocks)
    formatted = escape(message).replace(escape(heading), '<b>' + escape(heading) + '</b>')
    for row in rows:
        block = 'Location: ' + row['centre'] + '\nAppointment date: ' + date.fromisoformat(row['date']).strftime('%d %B %Y')
        formatted = formatted.replace(escape(block), '<b>' + escape(block) + '</b>')
    failures = []
    for channel, send in [('email', lambda: send_email(message, subject='Austria visa bot: check status',
                                                     html=formatted.replace('\n', '<br>'))),
                          ('Telegram', lambda: send_telegram(formatted, html=True))]:
        try:
            send()
            print(channel + ' status accepted by provider.')
        except Exception:
            failures.append(channel)
            print(channel + ' status failed; check provider configuration.')
    if failures:
        raise RuntimeError('Status notification failed')

def leads(data, today=None):
    today = today or datetime.now(timezone.utc).date()
    if data.get('residence') != 'GB' or data.get('destination_filter') is not None:
        raise ValueError('Unexpected feed route')
    if not isinstance(data.get('slots'), list):
        raise ValueError('Missing slots array')
    rows = []
    for entry in data['slots']:
        code = entry.get('destination_country_code')
        if code != 'AT' or entry.get('visa_category') != 'TOURIST':
            continue
        count = entry.get('applicant_count')
        if type(count) is not int or count != 1:
            continue
        for centre in entry.get('centres', []):
            if centre.get('centre_id') not in {'london','manchester','edinburgh'}:
                continue
            # Predicted and unclassified availability must never trigger alerts.
            if centre.get('slot_type') != 'actual' or not centre.get('earliest_date'):
                continue
            when = datetime.strptime(centre['earliest_date'], '%d-%m-%Y').date()
            if not today <= when < date(2026, 11, 14):
                continue
            rows.append({'country': COUNTRIES[code], 'centre': centre['centre_id'].title(),
                         'date': when.isoformat(),
                         'applicants': count if type(count) is int else 'unknown',
                         'detailed_dates_present': bool(centre.get('actual_dates'))})
    return sorted(rows, key=lambda row: (row['date'], row['country'], row['centre']))

def main():
    if os.environ.get('LIVE_SCHENGEN_ENABLED') != 'true':
        raise ValueError('LIVE_SCHENGEN_ENABLED must be true')
    req = Request(URL, headers={'X-API-Key': required('PARSE_API_KEY'),
                                'Accept': 'application/json'})
    with urlopen(req, timeout=30) as response:
        raw = response.read(1048577)
    if len(raw) > 1048576:
        raise ValueError('Feed exceeds size limit')
    payload = json.loads(raw)
    rows = leads(payload.get('data', payload))
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    fresh = []
    keys = []
    for row in rows:
        key = 'one-applicant:' + hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        if key not in state:
            keys.append(key)
            fresh.append(row)
    print(json.dumps({'matching_leads':len(rows), 'new_leads':len(fresh), 'results':rows}, indent=2))
    checked = datetime.now(timezone.utc).isoformat()
    send_check_status(rows, fresh, checked)
    lines = ['LIVE THIRD-PARTY AUSTRIA AVAILABILITY LEADS',
             'Queried at ' + checked + ' (request time, not source observation time).',
             '', 'These are provider-reported earliest dates, not confirmed appointments.',
             'Filter: Austria only, 1 applicant, tourist visa, London / Manchester / Edinburgh.',
             'Verify dates, category and capacity on the official booking portal.', '',
             'Country | UK centre | Earliest date | Reported applicants']
    for row in fresh:
        lines.append(' | '.join(str(row[k]) for k in ['country','centre','date','applicants']))
    lines += ['', 'Source: Parse independent Atlys wrapper, not an official VFS API.',
              'Some results have empty detailed date lists. Source freshness is unverified.',
              'No booking has been made. Missing destinations do not prove no slots exist.',
              'Check every two hours; unchanged leads are suppressed.']
    def save():
        STATE.parent.mkdir(parents=True, exist_ok=True)
        temp = STATE.with_suffix('.tmp')
        temp.write_text(json.dumps(state, indent=2))
        temp.replace(STATE)
    if fresh:
        body = '\n'.join(lines)
        formatted = escape(body)
        for when in {row['date'] for row in fresh}:
            formatted = formatted.replace(escape(when), '<b>' + escape(when) + '</b>')
        send_email(body, subject='Austria live feed: 1 applicant - dates to verify',
                   html=formatted.replace('\n', '<br>'))
        for key in keys:
            state[key] = checked
        save()
        print('Live lead email accepted by SMTP. Final delivery not confirmed.')
    else:
        print('No new email leads.')
    notify_leads(rows, state, checked, save)
    template = os.environ.get('WHATSAPP_LIVE_CONTENT_SID', '').strip()
    if not template:
        print('WhatsApp pending: approved dynamic alert template required.')
        return
    pending = []
    receipts = []
    for row in rows:
        key = 'whatsapp-one:' + hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        if key not in state:
            pending.append(row)
            receipts.append(key)
    if pending:
        # Separate template secret prevents reuse of the fixed trial reminder.
        os.environ['TWILIO_CONTENT_SID'] = template
        message = '1 applicant; third-party leads, verify manually. '
        message += '; '.join(r['country'] + ', ' + r['centre'] + ', ' + r['date'] for r in pending[:5])
        if len(pending) > 5:
            message += '; plus ' + str(len(pending) - 5) + ' more in email.'
        send_whatsapp(message)
        for key in receipts:
            state[key] = checked
        save()
        print('Live WhatsApp accepted by Twilio. Final delivery not confirmed.')

if __name__ == '__main__':
    try:
        main()
    except HTTPError as error:
        print('Feed rejected request: HTTP ' + str(error.code))
        raise SystemExit(1)
    except Exception as error:
        print('Live lead check failed: ' + type(error).__name__)
        raise SystemExit(1)


