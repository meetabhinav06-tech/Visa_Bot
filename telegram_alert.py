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
        message = ('Schengen visa availability lead\n'
                   + row['country'] + ' | ' + row['centre'] + ' | ' + row['date']
                   + '\n1 applicant, tourist visa.\n'
                   'Third-party reported date; verify availability and capacity on the official booking portal. '
                   'Source freshness is unverified. No booking made.\nChecked: ' + checked)
        formatted = escape(message).replace(escape(row['date']), '<b>' + escape(row['date']) + '</b>')
        send_telegram(formatted, html=True)
        state[key] = checked
        save()
    print('Telegram check complete; accepted messages are saved to prevent repeats.')
