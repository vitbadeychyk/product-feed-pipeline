import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from scripts.epicentr.export_feed import build_feed


class UnifiedFeedTests(unittest.TestCase):
    def test_full_content_manual_overrides_and_removed_history(self):
        source = ET.fromstring('''<yml_catalog><shop><categories><category id="77">Авто</category></categories><offers><offer id="supplier-id" available="true"><article>SKU</article><price>999</price><currencyId>UAH</currencyId><categoryId>77</categoryId><name_ua>Авто</name_ua><description_ua>&lt;p&gt;Повний опис&lt;/p&gt;</description_ua><picture>https://example.com/a.jpg</picture><param name="Матеріал" lang="ua">Метал</param></offer></offers></shop></yml_catalog>''')
        manual = ET.fromstring('''<offers><defaults><categoryId>76</categoryId><category_name>Санки</category_name><currencyId>UAH</currencyId><description_ua>Опис</description_ua><params><param name="Колір">Синій</param></params></defaults><offer id="S52"><name_ua>Санки</name_ua><picture>https://example.com/s.jpg</picture><params><param name="Колір">Жовтий</param></params></offer></offers>''')
        products = {'SKU': {'available': 'true', 'price': 2000, 'price_old': 2600}, 'S52': {'available': 'false', 'price': 3990, 'price_old': 4490}, 'OLD': {'available': 'false', 'price': 100}}
        root = build_feed(source, manual, products)
        offers = {o.get('id'): o for o in root.findall('./shop/offers/offer')}
        self.assertEqual(set(offers), set(products))
        self.assertEqual(offers['SKU'].findtext('price'), '2000')
        self.assertEqual(offers['SKU'].findtext('param'), 'Метал')
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
