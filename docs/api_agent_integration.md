# Techtanium — Agent Integration API

**Version:** 1.0 (English)
**Audience:** Agents / channel partners (and the operations team acting on their behalf) who manage sub-merchants, view commissions, and configure differentiated fee & profit-share terms.
**Auth:** JWT Bearer token (obtained via the login endpoint).
**Base URL:** `https://api.techtanium.com` (replace with your assigned environment; local dev: `http://localhost:8002`)

This API follows REST conventions (DRF ViewSets). Resources support standard CRUD and are filterable/sortable where noted.

---

## 1. Authentication

All Agent API endpoints require a JWT bearer token.

### 1.1 Obtain a token

`POST /api/v1/admin/auth/login/`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account` | string | yes | System/agent-admin account. |
| `password` | string | yes | Password. |

**Response (200)**

```json
{
  "token": "<jwt-string>",
  "user_id": "uuid",
  "account": "agent_admin",
  "roles": ["agent_admin"]
}
```

> Use the `token` value in the `Authorization` header for all subsequent requests.

### 1.2 Using the token

Send the token in every request:

```
Authorization: Bearer <jwt-string>
```

Tokens are validated on each request; an invalid/expired token returns `401 Unauthorized`. (A `logout` endpoint and a `me` endpoint are also available under `/api/v1/admin/auth/`.)

---

## 2. Conventions

- **Content-Type:** `application/json` for write operations.
- **Filtering:** list endpoints accept `?field=value` filters as documented per resource.
- **Search:** text search fields are matched case-insensitively.
- **Ordering:** pass `?ordering=-created_at` (prefix `-` for descending).
- **Soft delete:** the platform uses soft deletion; deleted records are excluded from list responses automatically.
- **Pagination:** large lists are returned as arrays (apply client-side paging if needed).

---

## 3. Endpoints

All paths are prefixed with `/api/v1/admin/`.

### 3.1 Agents — `/agents/`

Manage agent (channel-partner) profiles, status, and their linked merchants/commissions.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/agents/` | List agents (supports `?status=`, `?level=`, search, ordering). |
| `POST` | `/agents/` | Create an agent. `agent_no` is auto-generated. |
| `GET` | `/agents/{id}/` | Retrieve an agent. |
| `PUT`/`PATCH` | `/agents/{id}/` | Update an agent. |
| `DELETE` | `/agents/{id}/` | Soft-delete an agent. |
| `POST` | `/agents/{id}/suspend/` | Set status to `SUSPENDED`. |
| `POST` | `/agents/{id}/activate/` | Set status to `ACTIVE`. |
| `GET` | `/agents/{id}/merchants/` | List merchants linked to this agent. |
| `GET` | `/agents/{id}/commissions/` | List commission records for this agent. |

**Create agent — request body (key fields; `agent_no`, `created_at`, `updated_at` are server-generated):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_name` | string(≤128) | yes | Agent legal/display name. |
| `short_name` | string(≤64) | no | Short name. |
| `level` | enum | no | `LEVEL_1` / `LEVEL_2` / `LEVEL_3` (default `LEVEL_1`). |
| `status` | enum | no | `ACTIVE` / `SUSPENDED` / `CLOSED` (default `ACTIVE`). |
| `contact_name` | string | no | Contact person. |
| `contact_phone` | string | no | Contact phone. |
| `contact_email` | email | no | Contact email. |
| `commission_rate` | decimal | no | Default commission rate. |
| `max_merchant_count` | int | no | Max sub-merchants (0 = unlimited). |
| `legal_person` | string | no | Legal representative name (KYC). |
| `id_type` | string | no | ID document type (KYC). |
| `legal_person_id` | string | no | Legal person ID number (KYC). |
| `business_license_no` | string | no | Business license number (KYC). |
| `registered_capital` | string | no | Registered capital. |
| `registered_address` | string | no | Registered address. |
| `business_scope` | string | no | Business scope. |
| `established_date` | date | no | Establishment date. |
| `settlement_bank_name` | string | no | Settlement bank name. |
| `settlement_account_no` | string | no | Corporate settlement account number. |
| `swift_code` | string | no | SWIFT/BIC code. |
| `settlement_account_holder` | string | no | Settlement account holder. |
| `remark` | text | no | Remarks. |

**Response (201)** includes all fields plus `agent_no`, `merchant_count`, `total_commission`, `created_at`, `updated_at`.

---

### 3.2 Agent–Merchant Relations — `/agent-merchants/`

Link agents to the merchants they manage and set per-relation commission rates.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/agent-merchants/` | List relations (filter `?agent__agent_no=`, `?merchant__merchant_no=`). |
| `POST` | `/agent-merchants/` | Create a relation. |
| `GET` | `/agent-merchants/{id}/` | Retrieve. |
| `PUT`/`PATCH` | `/agent-merchants/{id}/` | Update. |
| `DELETE` | `/agent-merchants/{id}/` | Soft-delete. |

**Create — request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | id | yes | Agent id. |
| `merchant` | id | yes | Merchant id. |
| `commission_rate` | decimal | yes | Per-relation commission rate. |
| `effective_from` | date | yes | Relation start date. |
| `effective_to` | date | no | Relation end date (nullable). |

> A given (agent, merchant) pair may exist only once (`unique_together`); duplicates return `DUPLICATE_RELATION`.

---

### 3.3 Agent Commissions — `/agent-commissions/`

Read-only ledger of commission records generated per agent/merchant.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/agent-commissions/` | List commissions (filter `?agent__agent_no=`, `?merchant__merchant_no=`, `?status=`). |

**Fields returned:** `commission_no`, `agent`, `merchant`, `agent_name`, `merchant_name`, `order_count`, `total_amount`, `commission_amount`, `status`, `settle_date`, `paid_at`, `remark`, `created_at`.

> This is a **read-only** resource — commissions are generated by the platform, not created via API.

---

### 3.4 Agent Fee Configs — `/agent-fee-configs/`

Configure differentiated fee rates and profit-share terms per agent / fee type / currency.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/agent-fee-configs/` | List configs (filter `?agent__agent_no=`, `?fee_type=`, `?currency=`, `?is_active=`). |
| `POST` | `/agent-fee-configs/` | Create a config. |
| `GET` | `/agent-fee-configs/{id}/` | Retrieve. |
| `PUT`/`PATCH` | `/agent-fee-configs/{id}/` | Update. |
| `DELETE` | `/agent-fee-configs/{id}/` | Soft-delete. |
| `GET` | `/agent-fee-configs/stats/?agent_id=` | Aggregate stats (counts & covered currencies/fee types). |
| `POST` | `/agent-fee-configs/{id}/toggle/` | Enable/disable a config (`is_active` flips). |

**Create — request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | id | yes | Agent id. |
| `fee_type` | enum | yes | `TRANSACTION` / `SETTLEMENT` / `SERVICE`. |
| `currency` | enum | yes | `USD` / `EUR` / `GBP` / `CNY` / `JPY` / `HKD`. |
| `rate` | decimal | yes | Percentage rate, e.g. `0.5` = 0.5%. |
| `fixed_fee` | decimal | yes | Fixed fee per transaction. |
| `min_amount` | decimal | yes | Minimum charge. |
| `max_amount` | decimal | yes | Maximum charge (`0` = no cap). |
| `is_active` | bool | no | Default `true`. |
| `remark` | text | no | Remarks. |

> `(agent, fee_type, currency)` is unique — one config per combination.

**`stats` response (200)**

```json
{
  "total_configs": 12,
  "active_configs": 10,
  "covered_currencies": ["USD", "CNY", "EUR"],
  "covered_fee_types": ["TRANSACTION", "SETTLEMENT"],
  "currency_count": 3,
  "fee_type_count": 2
}
```

---

## 4. Enumerations

### 4.1 Agent

| Field | Values |
|-------|--------|
| `level` | `LEVEL_1`, `LEVEL_2`, `LEVEL_3` |
| `status` | `ACTIVE`, `SUSPENDED`, `CLOSED` |

### 4.2 Agent Fee Config

| Field | Values |
|-------|--------|
| `fee_type` | `TRANSACTION` (transaction fee), `SETTLEMENT` (settlement fee), `SERVICE` (service fee) |
| `currency` | `USD`, `EUR`, `GBP`, `CNY`, `JPY`, `HKD` |

### 4.3 Agent Commission

| Field | Values |
|-------|--------|
| `status` | `PENDING` (awaiting settlement), `SETTLED` (settled), `PAID` (paid) |

---

## 5. Examples

### 5.1 Obtain token and list agents

```python
import requests

BASE = "https://api.techtanium.com"
login = requests.post(f"{BASE}/api/v1/admin/auth/login/", json={
    "account": "agent_admin",
    "password": "your_password"
}).json()
token = login["token"]
headers = {"Authorization": f"Bearer {token}"}

# list active agents, newest first
r = requests.get(f"{BASE}/api/v1/admin/agents/",
                 headers=headers,
                 params={"status": "ACTIVE", "ordering": "-created_at"})
for a in r.json():
    print(a["agent_no"], a["agent_name"], "merchants:", a["merchant_count"])
```

### 5.2 Create a fee config for an agent

```python
payload = {
    "agent": 7,                 # agent id from the list above
    "fee_type": "TRANSACTION",
    "currency": "USD",
    "rate": "0.5",
    "fixed_fee": "0.30",
    "min_amount": "0.00",
    "max_amount": "0.00"
}
r = requests.post(f"{BASE}/api/v1/admin/agent-fee-configs/",
                  headers=headers, json=payload)
print(r.status_code, r.json())
```

### 5.3 Toggle a fee config off

```python
r = requests.post(f"{BASE}/api/v1/admin/agent-fee-configs/42/toggle/", headers=headers)
print(r.json())   # {"message": "Fee config disabled", "is_active": false}
```

---

*For accepting payments (pre-order, order query, refund), see the **Merchant (Customer) Integration API** document.*
