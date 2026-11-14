import io
import unittest
from unittest.mock import patch
from docx import Document
from PIL import Image
from app import app

class ExpenseTests(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()
        self.data={'recipient':'Oren','currency':'CAD','rows':[{'Receipt':'a.jpg','Date':'2026-11-14','Merchant':'Shop','Category':'Company Supplies','Currency':'CAD','Receipt Total':'20.10','Excluded Amount':'2.10','Notes':'Drink incl. HST'},{'Receipt':'b.jpg','Date':'2026-11-13','Category':'Trip Meals','Receipt Total':'10.01','Excluded Amount':0}]}
    def test_preview_exports(self):
        r=self.client.post('/api/expenses/report',json=self.data)
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['total'],28.01);self.assertIn('Excluded Personal Expenses',r.json['html'])
        self.assertLess(r.json['html'].index('November 13'),r.json['html'].index('November 14'))
        word=self.client.post('/api/expenses/report',json={**self.data,'format':'docx'})
        self.assertEqual(word.status_code,200)
        doc=Document(io.BytesIO(word.data));self.assertEqual(len(doc.tables),3)
        self.assertIn('28.01',' '.join(c.text for t in doc.tables for row in t.rows for c in row.cells))
        pdf=self.client.post('/api/expenses/report',json={**self.data,'format':'pdf'});self.assertTrue(pdf.data.startswith(b'%PDF'))
        with open('/workspace/scratch/35f2fe03da48/expense_test.docx','wb') as f:f.write(word.data)
    def test_exclusions_and_validation(self):
        self.data['rows'][0]['Excluded Amount']=100
        r=self.client.post('/api/expenses/report',json=self.data)
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['total'],10.01);self.assertEqual(r.json['excluded'],20.1)
        self.assertIn('20.10',r.json['html'])
        for val in ['NaN','Infinity','-1','bad']:
            self.data['rows'][0]['Receipt Total']=val
            self.assertEqual(self.client.post('/api/expenses/report',json=self.data).status_code,400)
        self.data['rows'][0]['Receipt Total']=20
        self.data['rows'][0]['Currency']='USD'
        self.assertEqual(self.client.post('/api/expenses/report',json=self.data).status_code,400)
    def test_safety_and_optional_exclusions(self):
        self.data['recipient']='<script>alert(1)</script>'
        self.data['include_excluded']=False
        r=self.client.post('/api/expenses/report',json=self.data)
        self.assertIn('&lt;script&gt;',r.json['html']);self.assertNotIn('Excluded Personal Expenses',r.json['html'])
        self.data['rows'][0]['Date']='bad date'
        self.assertEqual(self.client.post('/api/expenses/report',json=self.data).status_code,400)
    def test_extraction_endpoint(self):
        image=io.BytesIO();Image.new('RGB',(80,80),'white').save(image,'PNG');image.seek(0)
        extracted={'date':'2026-11-14','merchant':'Store','category':'Company Supplies','currency':'CAD','receipt_total':12.34,'possible_excluded_items':[{'item':'Drink','estimated_amount_including_tax':2,'reason':'Possible personal item'}],'notes':''}
        with patch('app.OpenAI'),patch.dict('os.environ',{'OPENAI_API_KEY':'test'}),patch('expenses.extract_receipt_information',return_value=extracted):
            r=self.client.post('/api/expenses/extract',data={'receipt':(image,'receipt.png')})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['row']['Excluded Amount'],0);self.assertIn('Drink',r.json['row']['Notes'])
    def test_page_integration(self):
        r=self.client.get('/');self.assertIn(b'Expense Report</option>',r.data);self.assertIn(b'expense-fields',r.data)
