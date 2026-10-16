import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from scripts.epicentr.export_feed import build_feed, build_supplier_content
from scripts.common import product_descriptions as descriptions
from unittest.mock import patch, Mock


class UnifiedFeedTests(unittest.TestCase):
    def test_direct_supplier_data_and_all_parameters(self):
        raw = ET.fromstring("""<root><catalog><category id="77">Електромобілі</category></catalog><items><item id="123"><vendorCode> SKU </vendorCode><name>Авто</name><name_ua>Машина</name_ua><categoryId>77</categoryId><vendor>Brand</vendor><barcode>12345</barcode><url>https://example.com/car</url><image>https://example.com/photo</image><description>Short supplier description</description><param name="Потужність" unit="Вт"><value lang="uk">100</value><value lang="ru">100</value></param><param name="Унікальна функція">Так</param></item><item><vendorCode>NO-DESCRIPTION</vendorCode></item></items></root>""")
        result = build_supplier_content(raw, {"sku": "<p>Full database description</p>"})
        offers = result.findall('./shop/offers/offer')
        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.findtext('description_ua'), '<p>Full database description</p>')
        self.assertEqual(offer.findtext('vendor'), 'Brand')
        self.assertEqual(offer.findtext('barcode'), '12345')
        self.assertEqual(offer.findtext('picture'), 'https://example.com/photo')
        self.assertEqual(result.findtext('./shop/categories/category'), 'Електромобілі')
        params = offer.findall('param')
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0].attrib, {'name': 'Потужність', 'unit': 'Вт', 'lang': 'ua'})
        self.assertEqual(params[-1].text, 'Так')
        self.assertFalse(any(p.get('name') == 'Гарантія' for p in params))

    def test_independent_database_request_and_sku_normalization(self):
        response = Mock()
        response.json.return_value = [{'sku': ' SKU ', 'description': 'Повний опис'}]
        with patch.object(descriptions, 'SUPABASE_URL', 'https://test.supabase.co'), patch.object(descriptions, 'SUPABASE_KEY', 'test-key'), patch.object(descriptions.requests, 'get', return_value=response) as get:
            result = descriptions.load_supabase_descriptions()
        self.assertIn('sku', result)
        self.assertEqual(get.call_args.args[0], 'https://test.supabase.co/rest/v1/products')
        self.assertEqual(get.call_args.kwargs['params']['select'], 'sku,description')

    def test_supplier_description_fallback_priority(self):
        raw = ET.fromstring("""<root><items>
        <item><vendorCode>DB</vendorCode><description_ua>Supplier UA</description_ua></item>
        <item><vendorCode>UA</vendorCode><description_ua>  &lt;p&gt;Український опис&lt;/p&gt;  </description_ua><description>Other</description></item>
        <item><vendorCode>RU</vendorCode><description_ua>  </description_ua><description>Supplier description</description></item>
        <item><vendorCode>NONE</vendorCode></item>
        </items></root>""")
        root = build_supplier_content(raw, {'db': 'Database description', 'ua': '  '})
        offers = {o.get('id'): o for o in root.findall('./shop/offers/offer')}
        self.assertEqual(offers['DB'].findtext('description_ua'), 'Database description')
        self.assertEqual(offers['UA'].findtext('description_ua'), '<p>Український опис</p>')
        self.assertEqual(offers['RU'].findtext('description_ua'), 'Supplier description')
        self.assertNotIn('NONE', offers)
        # All-empty descriptions in the DB still allow supplier descriptions.
        response = Mock()
        response.json.return_value = [{'sku': 'UA', 'description': None}]
        with patch.object(descriptions, 'SUPABASE_URL', 'https://test.supabase.co'), patch.object(descriptions, 'SUPABASE_KEY', 'test-key'), patch.object(descriptions.requests, 'get', return_value=response):
            self.assertEqual(descriptions.load_supabase_descriptions(allow_empty=True), {})

    def test_full_content_manual_overrides_and_removed_history(self):
        source = ET.fromstring('''<yml_catalog><shop><categories><category id="77">Авто</category></categories><offers><offer id="supplier-id" available="true"><article>SKU</article><price>999</price><currencyId>UAH</currencyId><categoryId>77</categoryId><name_ua>Авто</name_ua><description_ua>&lt;p&gt;Повний опис&lt;/p&gt;</description_ua><picture>https://example.com/a.jpg</picture><param name="Матеріал" lang="ua">Метал</param></offer></offers></shop></yml_catalog>''')
        manual = ET.fromstring('''<offers><defaults><categoryId>76</categoryId><category_name>Санки</category_name><currencyId>UAH</currencyId><description_ua>Опис</description_ua><params><param name="Колір">Синій</param></params></defaults><offer id="S52"><name_ua>Санки</name_ua><picture>https://example.com/s.jpg</picture><params><param name="Колір">Жовтий</param></params></offer></offers>''')
        products = {'SKU': {'available': 'true', 'price': 2000, 'price_old': 2600}, 'S52': {'available': 'false', 'price': 3990, 'price_old': 4490}, 'OLD': {'available': 'false', 'price': 100}}
        root = build_feed(source, manual, products)
        offers = {o.get('id'): o for o in root.findall('./shop/offers/offer')}
        self.assertEqual(set(offers), set(products))
        self.assertEqual(offers['SKU'].findtext('price'), '2000')
        self.assertEqual(offers['SKU'].findtext('priceOld'), '2600')
        self.assertEqual(offers['SKU'].findtext('priceOld'), offers['SKU'].findtext('price_old'))
        self.assertEqual(offers['SKU'].findtext('param'), 'Метал')
        self.assertEqual(offers['SKU'].findtext('country_of_origin'), 'Китай')
        self.assertEqual(offers['S52'].findtext('country_of_origin'), 'Україна')
        self.assertEqual(offers['S52'].findtext('param'), 'Жовтий')
        self.assertEqual(offers['OLD'].findtext('availability'), 'out_of_stock')
        ET.fromstring(ET.tostring(root))
        # Removed supplier product retains the entire last full card.
        history = deepcopy(products['SKU'])
        history['available'] = 'false'
        again = build_feed(ET.fromstring('<yml_catalog><shop/></yml_catalog>'), manual, {'SKU': history})
        removed = again.find('./shop/offers/offer')
        self.assertEqual(removed.get('available'), 'false')
        self.assertEqual(removed.findtext('description_ua'), '<p>Повний опис</p>')
        self.assertEqual(again.findtext('./shop/categories/category'), 'Авто')


if __name__ == '__main__':
    unittest.main()
