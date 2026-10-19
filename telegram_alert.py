"""Private Telegram notifications; credentials come only from environment secrets."""
import json
import os
from html import escape
from urllib.request import Request, urlopen


def send_telegram(message, html=False):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat:
        raise ValueError('Telegram token and chat ID required')
    # Short plain-text messages avoid formatting injection and Telegram size limits.
    if len(message) > 4000:
        raise ValueError('Telegram message too long')
    payload = {'chat_id': chat, 'text': message}
    if html:
        payload['parse_mode'] = 'HTML'
    request = Request('https://api.telegram.org/bot' + token + '/sendMessage',
                      data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get('ok') is not True:
        raise ValueError('Telegram rejected message')


def notify_leads(rows, state, checked, save):
    import hashlib
    if not os.environ.get('TELEGRAM_BOT_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID'):
        print('Telegram pending: add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets.')
        return
    for row in rows:
        key = 'telegram-one:' + hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        if key in state:
            continue
        from datetime import date
        when = date.fromisoformat(row['date']).strftime('%d %B %Y')
        message = ('<b>AUSTRIA: NEW AVAILABILITY LEAD</b>\n\n'
                   '<b>Location: ' + escape(row['centre']) + '\nAppointment date: ' + escape(when) + '</b>\n\n'
                   'Applicants: 1 | Visa: Tourist\n\n'
                   'Please verify availability and capacity on the official booking portal before booking. '
                   'This is third-party information; freshness is unverified. No booking made.\n\n'
                   'Checked (UTC): ' + escape(checked))
        send_telegram(message, html=True)
        state[key] = checked
        save()
    print('Telegram check complete; accepted messages are saved to prevent repeats.')
