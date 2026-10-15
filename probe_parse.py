"""One read-only Parse feed evaluation. Never sends alerts or enables monitoring."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

URL = ('https://api.parse.bot/scraper/1191f0c3-adff-47d9-abe0-a8155da12958/'
       'list_slots?residence=GB')

def main():
    key = os.environ.get('PARSE_API_KEY', '').strip()
    if not key:
        raise ValueError('Set PARSE_API_KEY in your environment or GitHub Secrets')
    request = Request(URL, headers={'X-API-Key': key, 'Accept': 'application/json'})
    with urlopen(request, timeout=30) as response:
        raw = response.read(1048577)
    if len(raw) > 1048576:
        raise ValueError('Unexpectedly large response')
    payload = json.loads(raw)
    data = payload.get('data', payload)
    if data.get('residence') != 'GB' or data.get('destination_filter') is not None:
        raise ValueError('Response did not confirm the UK all-destination query')
    rows = []
    for entry in data.get('slots', []):
        for centre in entry.get('centres', []):
            rows.append({
                'destination': entry.get('destination_country_code'),
                'centre': centre.get('centre_name'),
                'centre_id': centre.get('centre_id'),
                'category': entry.get('visa_category'),
                'reported_applicant_count': entry.get('applicant_count'),
                'slot_type': centre.get('slot_type'),
                'actual_dates': centre.get('actual_dates', []),
                'earliest_date': centre.get('earliest_date'),
                'predicted_dates_ignored': centre.get('predicted_dates', []),
            })
    report = {
        'purpose': 'FEED EVALUATION ONLY. No alerts sent.',
        'source': 'Parse third-party Atlys wrapper; not an official VFS API',
        'route': 'GB -> all reported destinations',
        'total_destinations': data.get('total_destinations'),
        'results': rows,
        'limitations': [
            'Empty results do not prove that VFS has no appointments.',
            'No source observation timestamp is documented in the listed schema.',
            'Applicant-count meaning and two-person coverage require confirmation.',
            'Predicted dates are not confirmed available appointments.',
            'A successful API response does not establish upstream authorisation.',
        ],
    }
    Path('feed-evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    try:
        main()
    except HTTPError as error:
        print('Feed request rejected: HTTP ' + str(error.code) + '. No alerts sent.')
        raise SystemExit(1)
    except Exception as error:
        print('Feed evaluation failed: ' + type(error).__name__ + '. No alerts sent.')
        raise SystemExit(1)
