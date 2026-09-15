from rest_framework.test import APITestCase


class AnonymousAccessRegressionTests(APITestCase):
    def assert_standard_unauthorized(self, response, scheme):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], scheme)
        self.assertEqual(
            set(response.data),
            {"code", "message", "field", "details", "request_id"},
        )
        self.assertTrue(response.data["request_id"])

    def test_admin_api_requires_bearer_authentication(self):
        response = self.client.get("/api/v1/admin/merchants/")
        self.assert_standard_unauthorized(response, "Bearer")

    def test_customer_profile_requires_bearer_authentication(self):
        response = self.client.get("/api/v1/user/profile/me/")
        self.assert_standard_unauthorized(response, "Bearer")

    def test_openapi_requires_hmac_authentication(self):
        response = self.client.post("/api/v1/payment/pre-order/", {}, format="json")
        self.assert_standard_unauthorized(response, "HMAC")

    def test_api_documentation_remains_public(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
