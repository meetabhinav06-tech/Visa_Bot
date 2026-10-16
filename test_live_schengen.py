from datetime import date
import unittest
from live_schengen import leads

class LeadTests(unittest.TestCase):
    def test_only_actual_schengen_tourist_and_before_departure(self):
        def entry(code='FI', category='TOURIST', slot='actual', when='23-10-2026'):
            return {'destination_country_code':code, 'visa_category':category,
                    'applicant_count':1,'centres':[{'centre_id':'london',
                    'slot_type':slot,'earliest_date':when,'actual_dates':[]}]}
        data={'residence':'GB','slots':[entry(),entry(code='TR'),
              entry(category='BUSINESS'),entry(slot='predicted'),
              entry(when='15-11-2026'),entry(when='01-10-2026')]}
        result=leads(data,date(2026,10,16))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['applicants'],1)
        self.assertFalse(result[0]['detailed_dates_present'])

    def test_wrong_route_fails(self):
        with self.assertRaises(ValueError):
            leads({'residence':'IN','slots':[]})

    def test_two_or_unknown_applicant_counts_excluded(self):
        for count in [2, None, '1', True]:
            data = {'residence':'GB', 'slots':[{'destination_country_code':'FI',
                    'visa_category':'TOURIST', 'applicant_count':count,
                    'centres':[{'centre_id':'london','slot_type':'actual',
                                'earliest_date':'23-10-2026'}]}]}
            self.assertEqual(leads(data,date(2026,10,16)),[])
