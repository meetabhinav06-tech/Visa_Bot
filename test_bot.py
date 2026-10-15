import copy
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch
import bot

class BotTests(unittest.TestCase):
    def setUp(self):
        self.feed = json.loads(bot.Path('sample-feed.json').read_text())
        self.now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)

    def test_capacity_and_centres(self):
        self.assertEqual([s['centre'] for s in bot.candidates(self.feed, self.now)], ['London', 'Edinburgh'])

    def test_stale_or_wrong_feed_rejected(self):
        for field, value in [('checked_at', '2026-10-14T12:00:00Z'), ('destination', 'FRA')]:
            feed = copy.deepcopy(self.feed)
            feed[field] = value
            with self.assertRaises(ValueError):
                bot.candidates(feed, self.now)

    def test_past_and_after_departure_excluded(self):
        for when in ['2026-10-14T09:00:00Z', '2026-11-14T09:00:00Z']:
            self.feed['slots'][0]['starts_at'] = when
            self.assertEqual(len(bot.candidates(self.feed, self.now)), 1)

    def test_partial_failure_retries_only_failed_channel(self):
        state = {}
        slot = self.feed['slots'][:1]
        with patch('bot.send_email') as email, patch('bot.send_whatsapp', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                bot.notify_slots(slot, ['email', 'whatsapp'], state, lambda _: None)
            self.assertEqual(email.call_count, 1)
        with patch('bot.send_email') as email, patch('bot.send_whatsapp') as whatsapp:
            bot.notify_slots(slot, ['email', 'whatsapp'], state, lambda _: None)
            email.assert_not_called()
            whatsapp.assert_called_once()

    def test_live_requires_explicit_permission(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                bot.load_feed()

    def test_live_rejects_simulation(self):
        from io import BytesIO
        response = BytesIO(json.dumps(self.feed).encode())
        response.geturl = lambda: 'https://example.com/feed'
        env = {'LIVE_ENABLED': 'true', 'SOURCE_AUTHORISED': 'true',
               'SOURCE_PERMISSION_REFERENCE': 'written permission', 'FEED_URL': 'https://example.com/feed'}
        with patch.dict('os.environ', env, clear=True), patch('bot.open_feed', return_value=response):
            with self.assertRaises(ValueError):
                bot.load_feed()

if __name__ == '__main__':
    unittest.main()
