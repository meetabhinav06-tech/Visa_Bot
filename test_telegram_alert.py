import os
import unittest
from unittest.mock import patch
from telegram_alert import notify_leads, send_telegram


class TelegramTests(unittest.TestCase):
    def test_failed_send_is_retried_and_success_is_not_repeated(self):
        row = {'country':'Finland', 'centre':'London', 'date':'2026-10-23', 'applicants':1}
        state = {}
        saved = []
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN':'test', 'TELEGRAM_CHAT_ID':'123'}):
            with patch('telegram_alert.send_telegram', side_effect=ValueError('failed')):
                with self.assertRaises(ValueError):
                    notify_leads([row], state, 'now', lambda: saved.append(True))
            self.assertEqual(state, {})
            with patch('telegram_alert.send_telegram') as send:
                notify_leads([row], state, 'now', lambda: saved.append(True))
                notify_leads([row], state, 'later', lambda: saved.append(True))
                self.assertEqual(send.call_count, 1)
                self.assertIn('verify availability', send.call_args.args[0])
            self.assertEqual(saved, [True])

    def test_api_rejection_does_not_report_success(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN':'test', 'TELEGRAM_CHAT_ID':'123'}):
            with patch('telegram_alert.urlopen') as fetch:
                fetch.return_value.__enter__.return_value.read.return_value = b'{"ok":false}'
                with self.assertRaises(ValueError):
                    send_telegram('test')
