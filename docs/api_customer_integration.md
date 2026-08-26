# Techtanium — Merchant (Customer) Integration API

**Version:** 1.0 (English)
**Audience:** Merchants / technical integrators who embed Techtanium payment acceptance into their own systems.
**Auth:** HMAC-SHA256 signed requests (per-merchant API Key + Secret).
**Base URL:** `https://api.techtanium.com` (replace with your assigned environment; local dev: `http://localhost:8002`)

All request and response bodies are JSON (`Content-Type: application/json`). Amounts are returned as **strings** to preserve decimal precision — parse them as `Decimal`/`BigDecimal` on your side.

---

## 1. Authentication

Every call (except the login endpoint in the Agent API) must be signed with your merchant credentials.

### 1.1 Credentials
You receive two values when your merchant account is created:
- **API Key** (`api_key`) — sent in the `X-Api-Key` header, used to identify your merchant.
- **API Secret** (`api_secret`) — used only to compute the signature, **never** sent over the wire.

### 1.2 Required headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Api-Key` | yes | Your merchant API Key. |
| `X-Timestamp` | yes | Unix timestamp in **seconds** (UTC). |
| `X-Nonce` | yes | A random string; must be unique per request. |
| `X-Signature` | yes | HMAC-SHA256 signature (hex), lowercase. |
| `Content-Type` | yes | `application/json`. |

### 1.3 Signature algorithm

The signature string is built from the request in this exact order:

```
sign_string = API_KEY + TIMESTAMP + NONCE + METHOD + PATH
if query_string:
    sign_string += "?" + query_string        # GET params, keys sorted ascending, joined "k=v&..."
if body:
    sign_string += body                       # raw request body (verbatim)
signature  = HMAC_SHA256(API_SECRET, sign_string)   # hex digest, lowercase
```

Notes:
- `METHOD` is the uppercase HTTP verb (`GET` / `POST`).
- `PATH` is the path only, **without** the query string (e.g. `/api/v1/payment/orders/`).
- For `GET` requests the raw body is empty, so only the query string (if any) is appended.
- `TIMESTAMP` is valid within **±300 seconds** of server time; otherwise the request is rejected as expired.
- `NONCE` is accepted only once per API Key within the 300-second window (replay protection).

### 1.4 Python signing example

```python
import hmac, hashlib, time, uuid, requests, json

API_KEY = "ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
API_SECRET = "your_api_secret_here"
BASE = "https://api.techtanium.com"

def signed_request(method, path, params=None, json_body=None):
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    url = BASE + path

    # query string (sorted) for signing
    query_string = ""
    if params:
        qs = "&".join(f"{k}={params[k]}" for k in sorted(params))
        query_string = "?" + qs

    body = json.dumps(json_body, separators=(",", ":"), ensure_ascii=False) if json_body else ""

    sign_str = API_KEY + ts + nonce + method.upper() + path + query_string + body
    signature = hmac.new(API_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-Api-Key": API_KEY,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }
    return requests.request(method, url, params=params, data=body, headers=headers)
```

---

## 2. Common response format

Successful responses carry a top-level `"code": "SUCCESS"` plus the resource fields. Example:

```json
{
  "code": "SUCCESS",
  "order_no": "PO202608070001",
  "amount": "1000.00",
  "fee_amount": "5.00",
  "settle_amount": "995.00",
  "status": "PENDING_REVIEW"
}
```

Errors use the same envelope with an error `code` and human-readable `message`, plus an HTTP status:

```json
{ "code": "ORDER_NOT_FOUND", "message": "Order not found" }
```

### 2.1 Standard error codes

| HTTP | `code` | Meaning |
|------|--------|---------|
| 401 | `AUTH_FAILED` | Missing/invalid signature, expired timestamp, or reused nonce. |
| 400 | `ORDER_NO_REQUIRED` | `order_no` was required but not provided. |
| 404 | `ORDER_NOT_FOUND` | No order matches the given `order_no` for this merchant. |
| 400 | `VALIDATION_ERROR` | Request body failed validation (e.g. amount ≤ 0). |
| 409 | `DUPLICATE_* / IDEMPOTENT` | Conflicting or duplicate request (idempotency key already used). |
| 4xx/5xx | business-specific | Returned by `BusinessException` (e.g. `MERCHANT_NOT_FOUND`, `FEE_NOT_CONFIGURED`). |

> **Localization note:** a small number of success/status `message` strings on the server are still being standardized to English (e.g. the close-order response currently returns `"订单已关闭"`). The `code` field is always a stable English enum and is the recommended value to branch on.

---

## 3. Endpoints

### 3.1 Create Pre-order
`POST /api/v1/payment/pre-order/`

Creates a payment order. The `merchant_no` in the body is overwritten by the authenticated merchant, so it is accepted but ignored for security.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `merchant_no` | string | yes | Merchant number (ignored / re-bound to the signed merchant). |
| `merchant_order_no` | string(≤64) | yes | Your internal order id (idempotency per merchant). |
| `amount` | decimal | yes | Order amount. Must be > 0. |
| `currency` | string(3) | no | ISO 4217 currency, default `CNY`. |
| `pay_method` | enum | yes | `ONLINE_BANK` / `AUTHORIZED` / `WIRE_TRANSFER`. |
| `bank_code` | string(≤16) | no | Bank code for routing (optional). |
| `user_id` | string(≤64) | no | Your end-user identifier for this order. |
| `notify_url` | url(≤512) | no | Async callback URL for payment result. |
| `idempotency_key` | string(≤64) | no | Idempotency key; re-sending the same key returns the original order. |

**Response (201)**

```json
{
  "code": "SUCCESS",
  "order_no": "PO202608070001",
  "unique_identification_no": "UID-9F2A1C",
  "amount": "1000.00",
  "fee_amount": "5.00",
  "settle_amount": "995.00",
  "status": "PENDING_REVIEW",
  "expire_at": "2026-08-07T12:00:00Z",
  "created_at": "2026-08-07T11:00:00Z"
}
```

---

### 3.2 List Orders
`GET /api/v1/payment/orders/`

**Query parameters**

| Param | Type | Description |
|-------|------|-------------|
| `merchant_order_no` | string | Optional filter by your internal order id. |

**Response (200)** — returns up to the 50 most recent orders.

```json
{
  "code": "SUCCESS",
  "count": 2,
  "results": [
    {
      "order_no": "PO202608070001",
      "merchant_order_no": "M-1001",
      "amount": "1000.00",
      "fee_amount": "5.00",
      "status": "COMPLETED",
      "pay_method": "WIRE_TRANSFER",
      "created_at": "2026-08-07T11:00:00Z"
    }
  ]
}
```

---

### 3.3 Query Order
`GET /api/v1/payment/orders/{order_no}/`

**Response (200)**

```json
{
  "code": "SUCCESS",
  "order_no": "PO202608070001",
  "merchant_order_no": "M-1001",
  "amount": "1000.00",
  "currency": "USD",
  "fee_amount": "5.00",
  "settle_amount": "995.00",
  "status": "COMPLETED",
  "pay_method": "WIRE_TRANSFER",
  "unique_identification_no": "UID-9F2A1C",
  "pay_received_at": "2026-08-07T11:30:00Z",
  "settled_at": "2026-08-07T11:35:00Z",
  "created_at": "2026-08-07T11:00:00Z",
  "expire_at": "2026-08-07T12:00:00Z"
}
```

---

### 3.4 Close Order
`POST /api/v1/payment/orders/{order_no}/close/`

Closes an unpaid/unprocessed order. Returns `code: SUCCESS` with a status message.

**Response (200)** — `{ "code": "SUCCESS", "message": "Order closed" }`

---

### 3.5 Apply Refund
`POST /api/v1/refund/apply/`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `order_no` | string(≤32) | yes | The original paid order to refund. |
| `refund_amount` | decimal | yes | Refund amount. Must be > 0 and ≤ paid amount. |
| `reason` | string(≤256) | yes | Refund reason. |
| `idempotency_key` | string(≤64) | no | Idempotency key. |

**Response (201)**

```json
{
  "code": "SUCCESS",
  "refund_no": "RF202608070001",
  "refund_amount": "500.00",
  "refund_fee_rate": "0.000000",
  "refund_fee_amount": "0.00",
  "status": "PENDING_REVIEW",
  "created_at": "2026-08-07T11:40:00Z"
}
```

---

### 3.6 Query Refund
`GET /api/v1/refund/query/?order_no={order_no}`

**Response (200)**

```json
{
  "code": "SUCCESS",
  "count": 1,
  "results": [
    {
      "refund_no": "RF202608070001",
      "refund_amount": "500.00",
      "refund_fee_rate": "0.000000",
      "refund_fee_amount": "0.00",
      "refund_reason": "Customer request",
      "status": "SUCCESS",
      "reviewed_at": "2026-08-07T11:45:00Z",
      "refunded_at": "2026-08-07T11:50:00Z",
      "created_at": "2026-08-07T11:40:00Z"
    }
  ]
}
```

---

## 4. Enumerations

### 4.1 Order status (`status`)

| Value | Meaning |
|-------|---------|
| `PRE_CREATE` | Pre-created (not yet active). |
| `PENDING_REVIEW` | Awaiting review. |
| `PENDING_PAY` | Awaiting payment from payer. |
| `PAY_RECEIVED` | Payment received. |
| `PENDING_SETTLE` | Awaiting settlement. |
| `PROCESSING` | Being processed. |
| `SETTLED` | Settled. |
| `COMPLETED` | Completed. |
| `CLOSED` | Closed / cancelled. |

### 4.2 Payment method (`pay_method`)

| Value | Meaning |
|-------|---------|
| `ONLINE_BANK` | Online banking payment. |
| `AUTHORIZED` | Authorized (account-authorization) payment. |
| `WIRE_TRANSFER` | Wire / remittance transfer. |

### 4.3 Refund status (`status`)

| Value | Meaning |
|-------|---------|
| `PENDING_REVIEW` | Refund awaiting review. |
| `APPROVED` | Refund approved. |
| `REJECTED` | Refund rejected. |
| `PROCESSING` | Refund being processed. |
| `SUCCESS` | Refund succeeded. |
| `FAILED` | Refund failed. |

---

## 5. Webhook (Async Notification)

If you supplied `notify_url` at pre-order, Techtanium will `POST` the payment result to that URL (retried automatically). Treat the callback as a signal to re-query the order via **3.3 Query Order** to get the authoritative final status.

- Method: `POST`
- Content-Type: `application/json`
- Recommended: verify the order `status` from the query endpoint rather than trusting the callback body alone.

---

## 6. End-to-end example

```python
# 1) Pre-order
r = signed_request("POST", "/api/v1/payment/pre-order/", json_body={
    "merchant_no": "M202608070001",
    "merchant_order_no": "M-1001",
    "amount": "1000.00",
    "currency": "USD",
    "pay_method": "WIRE_TRANSFER",
    "notify_url": "https://your-domain.com/cb/techtanium"
})
order = r.json()
print(order["order_no"], order["status"])

# 2) Later, query the order
r2 = signed_request("GET", f"/api/v1/payment/orders/{order['order_no']}/")
print(r2.json()["status"])

# 3) Refund part of it
r3 = signed_request("POST", "/api/v1/refund/apply/", json_body={
    "order_no": order["order_no"],
    "refund_amount": "500.00",
    "reason": "Customer request"
})
print(r3.json()["refund_no"], r3.json()["status"])
```

---

*For partner/agent onboarding and commission management, see the **Agent Integration API** document.*
