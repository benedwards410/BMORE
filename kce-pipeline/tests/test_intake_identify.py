import unittest

from helpers.minipdf import make_pdf
from kce_intake.identify import Address, doc_type_hint, extract_addresses, find_mtx, is_pdf, pdf_text


class TestMtx(unittest.TestCase):
    def test_finds_and_normalises(self):
        self.assertEqual(find_mtx("MTX20616192  Bob Bell, MTX 79857647, mtx12345678, MTX20616192"),
                         ["MTX20616192", "MTX79857647", "MTX12345678"])

    def test_ignores_short_or_long(self):
        self.assertEqual(find_mtx("MTX1234 MTX123456789"), [])
        self.assertEqual(find_mtx(None), [])


class TestPdfText(unittest.TestCase):
    def test_reads_text_layer(self):
        data = make_pdf(["Proposal Detail Report for Fox Valley Homeowners Assoc",
                         "Audit / Proposal: MTX79857647 / Steve's Pools",
                         "3320 GREAT VALLEY Drive, West Friendship MD 21794"])
        self.assertTrue(is_pdf(data))
        text = pdf_text(data)
        self.assertEqual(find_mtx(text), ["MTX79857647"])
        self.assertIn(Address("3320", "great", None), extract_addresses(text))

    def test_garbage_is_empty(self):
        self.assertEqual(pdf_text(b"not a pdf"), "")
        self.assertEqual(pdf_text(b"%PDF-1.4 truncated"), "")


class TestAddresses(unittest.TestCase):
    def test_suite_forms(self):
        cases = {
            "Vacant 5114 A Dorsey Hall": Address("5114", "dorsey", "A"),
            "5114 Dorsey Hall Unit B Hair Salon": Address("5114", "dorsey", "B"),
            "1514 JABEZ Run SUITE 106 , Millersville MD 21108": Address("1514", "jabez", "106"),
            "Submit for payment- 11421 Cronhill Suite E": Address("11421", "cronhill", "E"),
            "Re: 9210 Baltimore national Pike": Address("9210", "baltimore", None),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, extract_addresses(text))

    def test_loose_only_on_request(self):
        self.assertEqual(extract_addresses("WO- 5124A Dorsey family dental"), set())
        self.assertIn(Address("5124", "dorsey", "A"), extract_addresses("WO- 5124A Dorsey family dental", loose=True))
        self.assertIn(Address("9631", "liberty", None), extract_addresses("9631 liberty N (vacant)", loose=True))

    def test_loose_skips_noise(self):
        found = extract_addresses("Smart Solutions Inc Invoice 1028 BGE Vacant Completed", loose=True)
        self.assertEqual(found, set())

    def test_compatibility(self):
        a = Address("5114", "dorsey", "A")
        b = Address("5114", "dorsey", "B")
        any_suite = Address("5114", "dorsey", None)
        self.assertFalse(a.compatible(b))
        self.assertTrue(a.compatible(any_suite))
        self.assertTrue(any_suite.compatible(b))
        self.assertFalse(a.compatible(Address("5116", "dorsey", "A")))

    def test_roundtrip(self):
        a = Address("1514", "jabez", "106")
        self.assertEqual(Address.from_dict(a.to_dict()), a)


class TestDocTypeHint(unittest.TestCase):
    def test_matrix_names(self):
        self.assertEqual(doc_type_hint("Participation Agreement-Solar Energy Services.pdf"), "participation_agreement")
        self.assertEqual(doc_type_hint("Proposal Detail-Solar Energy Services.pdf"), "proposal_detail")
        self.assertEqual(doc_type_hint("Detailed Cost-HBs to Strips (no vapors) (1).pdf"), "detailed_cost")
        self.assertEqual(doc_type_hint("Customer-Solar Energy Services.pdf"), "customer_packet")
        self.assertEqual(doc_type_hint("MD Works revised WO.pdf"), "work_order")

    def test_text_fallback(self):
        self.assertEqual(doc_type_hint("x.pdf", "Line 1 Material ... Program Share  Customer Share"), "detailed_cost")
        self.assertEqual(doc_type_hint("x.pdf", ""), "unknown")


if __name__ == "__main__":
    unittest.main()
