"""Regression tests for manual sled integration; no network or Supabase required."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts.rozetka.manual_sleds import append_manual_sleds


BASE_DIR = Path(__file__).resolve().parents[2]
MANUAL_FILE = BASE_DIR / "data/manual/epicentr_manual_products.xml"


class ManualSledsTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(
            '<yml_catalog><shop><categories><category id="46">Cars</category>'
            '</categories><offers><offer id="123" available="true">'
            '<article>EXISTING</article><price>9000</price>'
            '</offer></offers></shop></yml_catalog>'
        )
        self.original_offer = ET.tostring(self.root.find("./shop/offers/offer"))

    def test_real_manual_sleds_match_shared_source(self):
        manual = ET.parse(MANUAL_FILE).getroot()
        defaults = manual.find("defaults")
        count = append_manual_sleds(self.root)
        self.assertEqual(count, len(manual.findall("offer")))
        self.assertEqual(count, 31)
        self.assertEqual(
            ET.tostring(self.root.find("./shop/offers/offer")), self.original_offer
        )
        categories = self.root.findall("./shop/categories/category")
        self.assertEqual(sum(c.get("id") == "76" for c in categories), 1)

        for source in manual.findall("offer"):
            product_id = source.get("id")
            actual = self.root.find(f"./shop/offers/offer[@id='{product_id}']")
            self.assertIsNotNone(actual)
            available = source.get("available")
            self.assertEqual(actual.get("available"), available)
            self.assertEqual(
                actual.findtext("stock_quantity"), "10" if available == "true" else "0"
            )
            self.assertEqual(actual.findtext("price"), source.findtext("price") or defaults.findtext("price"))
            self.assertEqual(
                actual.findtext("price_old"),
                source.findtext("price_old") or defaults.findtext("price_old"),
            )
            self.assertEqual(actual.findtext("article"), source.findtext("article"))
            params = {
                param.get("name"): param.text
                for param in actual.findall("param")
            }
            self.assertEqual(params.get("Граничне навантаження"), "30 кг")
            self.assertEqual(params.get("Країна-виробник товару"), "Україна")

    def _expect_rejected_without_mutation(self, mutate):
        manual = ET.parse(MANUAL_FILE)
        mutate(manual.getroot())
        original = ET.tostring(self.root)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.xml"
            manual.write(path, encoding="utf-8")
            with self.assertRaises(ValueError):
                append_manual_sleds(self.root, path)
        self.assertEqual(ET.tostring(self.root), original)

    def test_duplicate_sku_rejected(self):
        self._expect_rejected_without_mutation(
            lambda root: root.findall("offer")[1].set(
                "id", root.findall("offer")[0].get("id")
            )
        )

    def test_invalid_availability_rejected(self):
        self._expect_rejected_without_mutation(
            lambda root: root.findall("offer")[0].set("available", "unknown")
        )

    def test_invalid_price_rejected(self):
        self._expect_rejected_without_mutation(
            lambda root: root.find("defaults/price").__setattr__("text", "bad-price")
        )

    def test_existing_sku_collision_rejected(self):
        self.root.find("./shop/offers/offer/article").text = "S50"
        self._expect_rejected_without_mutation(lambda _: None)


if __name__ == "__main__":
    unittest.main()
