"""Semantic search, OCR indexing, and watcher-state integration."""

import shutil
import unittest
from app.service import Application
from localdesk.safety import InputError
from tests.support import AppCase, ROOT
from tests.fixtures import make_image, make_pdf


class UpgradeTests(AppCase):
    def index_workspace(self, ocr=False):
        root = self.app.common_post(
            "roots/add", {"path": str(self.workspace), "ocr": ocr}
        )
        self.finish("scan", {"id": root["id"]})
        return root

    def test_hybrid_search_filters_by_type_and_tag(self):
        self.file(
            "payment.txt",
            "The supplier invoice payment is due. Supplier billing total and payment receipt.",
        )
        self.file("sport.md", "Football players train at a stadium.")
        self.index_workspace()
        result = self.app.common_get(
            "search", {"q": "supplier payment", "mode": "hybrid", "extension": ".txt"}
        )
        self.assertTrue(result["results"])
        self.assertTrue(all(r["extension"] == ".txt" for r in result["results"]))
        self.assertIn("fusion", result)

    def test_semantic_query_changes_ranking(self):
        self.file(
            "payment.txt",
            "Supplier invoices and payments account for the billing total.",
        )
        self.file("football.txt", "Football stadium goals players match and training.")
        self.file(
            "office.txt", "Supplier payment invoices include monthly account totals."
        )
        self.index_workspace()
        result = self.app.common_get(
            "search", {"q": "football goals", "mode": "semantic"}
        )
        self.assertEqual(result["results"][0]["name"], "football.txt")

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract integration dependency.")
    def test_ocr_index_finds_image_text(self):
        make_image(self.workspace / "image.png")
        self.index_workspace(ocr=True)
        result = self.app.common_get("search", {"q": "7316", "mode": "keyword"})
        self.assertEqual(result["results"][0]["name"], "image.png")

    def test_pdf_index_finds_native_text(self):
        make_pdf(self.workspace / "invoice.pdf")
        self.index_workspace()
        self.assertTrue(
            self.app.common_get("search", {"q": "Invoice", "mode": "keyword"})[
                "results"
            ]
        )

    def test_unknown_search_mode_is_rejected(self):
        with self.assertRaises(InputError):
            self.app.common_get("search", {"q": "test", "mode": "remote"})

    def test_model_selection_requires_existing_local_directory(self):
        with self.assertRaises((InputError, FileNotFoundError)):
            self.app.common_post(
                "semantic/model", {"path": str(self.base / "missing-model")}
            )

    def test_index_content_is_encrypted_after_restart(self):
        app = Application(
            ROOT, self.base / "encrypted", passphrase="synthetic search password"
        )
        try:
            app.store.set("secret", "PRIVATE_SEARCH_MARKER")
        finally:
            app.close()
        self.assertNotIn(
            b"PRIVATE_SEARCH_MARKER", (self.base / "encrypted/app.vault").read_bytes()
        )
        app = Application(
            ROOT, self.base / "encrypted", passphrase="synthetic search password"
        )
        try:
            self.assertEqual(app.store.get("secret"), "PRIVATE_SEARCH_MARKER")
        finally:
            app.close()
