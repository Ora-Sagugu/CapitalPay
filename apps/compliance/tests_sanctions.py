from django.test import TestCase

from apps.compliance.country_sanctions import detect_sanctioned_country
from apps.compliance.country_names import normalize_country_display
from apps.compliance.services import build_sanction_warning, scan_entity_lightweight


class CountryNameNormalizationTests(TestCase):
    def test_chinese_country_translated_to_english(self):
        self.assertEqual(normalize_country_display("伊朗"), "Iran")
        self.assertEqual(normalize_country_display("朝鲜"), "North Korea")
        self.assertEqual(normalize_country_display("中国"), "China")
        self.assertEqual(normalize_country_display("多国"), "Multiple")

    def test_english_country_passthrough(self):
        self.assertEqual(normalize_country_display("Iran"), "Iran")
        self.assertEqual(normalize_country_display("North Korea"), "North Korea")


class CountrySanctionsTests(TestCase):
    def test_detect_iran_in_name(self):
        hits = detect_sanctioned_country("Iran")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["country"], "Iran")
        self.assertEqual(hits[0]["match_type"], "country_name")

    def test_detect_north_korea_aliases(self):
        for text in ("North Korea", "DPRK", "朝鲜"):
            hits = detect_sanctioned_country(text)
            self.assertTrue(hits, msg=text)
            self.assertEqual(hits[0]["country"], "North Korea")

    def test_detect_iran_in_address(self):
        hits = detect_sanctioned_country("Tehran, Iran")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["country"], "Iran")


class ScanEntityLightweightCountryTests(TestCase):
    def test_name_only_iran_triggers_country_hit(self):
        result = scan_entity_lightweight("Iran", "")
        self.assertFalse(result["is_clear"])
        self.assertTrue(result["country_hits"])
        self.assertEqual(result["country_hits"][0]["country"], "Iran")

    def test_address_iran_triggers_country_hit(self):
        result = scan_entity_lightweight("John Smith", "Tehran, Iran")
        self.assertFalse(result["is_clear"])
        countries = {hit["country"] for hit in result["country_hits"]}
        self.assertIn("Iran", countries)

    def test_clear_name_has_no_hits(self):
        result = scan_entity_lightweight("John Smith", "London, UK")
        self.assertTrue(result["is_clear"])
        self.assertEqual(result["country_hits"], [])


class SanctionWarningMessageTests(TestCase):
    def test_build_warning_includes_country(self):
        message = build_sanction_warning([], [], [{
            "country": "Iran",
            "keyword": "Iran",
            "list_type": "OFAC/UN",
            "risk_level": "HIGH",
            "match_type": "country_name",
            "reason": "Comprehensive sanctions jurisdiction",
        }])
        self.assertIn("Iran", message)
        self.assertIn("OFAC/UN", message)


SAMPLE_SDN_CSV = (
    "ent_num,SDN_Name,SDN_Type,Program,Title,Call_Sign,Vess_type,Tonnage,GRT,Vess_flag,Vess_owner,Remarks\n"
    '53616,"DOE, John",individual,IRAN,-0-,-0-,-0-,-0-,-0-,-0-,-0-,"DOB 01 Jan 1970; nationality Iran;"\n'
)

SAMPLE_UN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST>
  <INDIVIDUALS>
    <INDIVIDUAL>
      <DATAID>1</DATAID>
      <FIRST_NAME>Ali</FIRST_NAME>
      <SECOND_NAME>Mohamed</SECOND_NAME>
      <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
      <REFERENCE_NUMBER>QDi.001</REFERENCE_NUMBER>
      <LISTED_ON>2001-10-17</LISTED_ON>
      <NATIONALITY>
        <VALUE>Iran</VALUE>
      </NATIONALITY>
      <COMMENTS1>Test listing</COMMENTS1>
    </INDIVIDUAL>
  </INDIVIDUALS>
</CONSOLIDATED_LIST>
"""


class SanctionFileImportApiTests(TestCase):
    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from rest_framework.test import APIClient

        from apps.compliance.models import SanctionList
        from apps.rbac.models import SystemUser
        from apps.rbac.services import AuthService

        self.SimpleUploadedFile = SimpleUploadedFile
        self.SanctionList = SanctionList
        self.client = APIClient()
        from apps.rbac.testing import attach_super_admin
        user = SystemUser.objects.create(
            username="sanction_ops",
            password_hash=AuthService._hash_password("Secret@123"),
            real_name="Ops",
        )
        attach_super_admin(user)
        self.client.force_authenticate(user)

    def _post(self, filename, content, list_type, content_type="text/plain"):
        upload = self.SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(
            "/api/v1/admin/sanction-lists/import-file/",
            {"list_type": list_type, "file": upload},
            format="multipart",
        )

    def test_import_ofac_sdn_csv(self):
        resp = self._post("SDN.CSV", SAMPLE_SDN_CSV.encode("utf-8"), "OFAC", "text/csv")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data["list_type"], "OFAC")
        self.assertGreaterEqual(data["created"], 1)
        self.assertEqual(self.SanctionList.objects.filter(list_type="OFAC").count(), data["created"])
        row = self.SanctionList.objects.get(list_type="OFAC")
        self.assertEqual(row.entity_name, "DOE, John")
        self.assertEqual(row.country, "Iran")

    def test_import_un_consolidated_xml(self):
        resp = self._post(
            "consolidated.xml",
            SAMPLE_UN_XML.encode("utf-8"),
            "UN",
            "application/xml",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data["list_type"], "UN")
        self.assertGreaterEqual(data["created"], 1)
        self.assertEqual(self.SanctionList.objects.filter(list_type="UN").count(), data["created"])
        row = self.SanctionList.objects.get(list_type="UN")
        self.assertEqual(row.entity_name, "Ali Mohamed")

    def test_wrong_extension_returns_400(self):
        resp = self._post("list.txt", SAMPLE_SDN_CSV.encode("utf-8"), "OFAC")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(self.SanctionList.objects.count(), 0)

    def test_empty_file_returns_400(self):
        resp = self._post("SDN.CSV", b"", "OFAC", "text/csv")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(self.SanctionList.objects.count(), 0)
