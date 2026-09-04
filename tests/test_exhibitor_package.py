import unittest

from pydantic import ValidationError

from app.main import app
from app.modules.iwbif.schemas import PackageCatalogRead, PackageRateWrite, PackageWrite


class ExhibitorPackageContractTests(unittest.TestCase):
    def test_exhibitor_package_is_optional(self):
        package = PackageWrite(
            code="EXHIBITOR", name="Exhibitor Package - USD200",
            package_type="exhibitor", selection_mode="optional", amount=200,
        )
        self.assertEqual("exhibitor", package.package_type)

    def test_exhibitor_package_cannot_be_required_main(self):
        with self.assertRaises(ValidationError):
            PackageWrite(
                code="EXHIBITOR", name="Exhibitor Package - USD200",
                package_type="exhibitor", selection_mode="required_one", amount=200,
            )

    def test_standard_rate_is_supported(self):
        rate = PackageRateWrite(
            occupancy_type="standard", name="Exhibitor Access", amount=200,
        )
        self.assertEqual("standard", rate.occupancy_type)

    def test_catalog_has_dedicated_exhibitor_group(self):
        catalog = PackageCatalogRead(main_packages=[], additional_packages=[])
        self.assertEqual([], catalog.exhibitor_packages)

    def test_exhibitor_uses_existing_package_crud_endpoints(self):
        paths = app.openapi()["paths"]
        collection = paths["/api/v1/admin/events/{event_id}/delegate-packages"]
        item = paths["/api/v1/admin/events/{event_id}/delegate-packages/{item_id}"]

        self.assertIn("post", collection)
        self.assertIn("get", item)
        self.assertIn("put", item)
        self.assertIn("delete", item)


if __name__ == "__main__":
    unittest.main()
