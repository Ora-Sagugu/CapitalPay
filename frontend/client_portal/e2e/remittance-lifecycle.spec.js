import { expect, test } from '@playwright/test'

async function expectOk(response) {
  const body = await response.json().catch(() => ({}))
  expect(response.ok(), JSON.stringify(body)).toBeTruthy()
  return body
}

test('two-stage review activates merchant and submits a quoted remittance', async ({ request, page }) => {
  const suffix = `${Date.now()}`.slice(-10)
  const username = `e2e_${suffix}`
  const email = `${username}@gmail.com`
  const password = 'E2ePass@123'

  const registration = await expectOk(await request.post('/api/v1/user/auth/register-email/', {
    data: { username, email, password, portal_role: 'customer' }
  }))
  const customerToken = registration.token

  await expectOk(await request.post('/api/v1/user/onboarding/submit/', {
    headers: { Authorization: `Bearer ${customerToken}` },
    data: {
      basic: {
        legal_name: `E2E Trading ${suffix}`,
        id_type: 'business_license',
        id_number: `LIC-${suffix}`,
        contact_phone: `2547${suffix}`,
        nationality: 'Kenya',
        address: '1 Test Avenue, Nairobi',
        agent_code: '',
        license_expiry_date: '2030-12-31'
      },
      finance: {
        bank_name: 'E2E Test Bank',
        branch_name: 'Nairobi',
        account_name: `E2E Trading ${suffix}`,
        bank_account: `001${suffix}`
      },
      images: {
        license_image: 'data:image/png;base64,AA==',
        id_front_image: 'data:image/png;base64,AA==',
        id_back_image: 'data:image/png;base64,AA=='
      }
    }
  }))

  const adminLogin = await expectOk(await request.post('/api/v1/admin/auth/login/', {
    data: { account: 'admin', password: '123456' }
  }))
  const adminHeaders = { Authorization: `Bearer ${adminLogin.token}` }

  const pendingList = await expectOk(await request.get('/api/v1/admin/onboarding/', {
    headers: adminHeaders,
    params: { status: 'pending', search: username }
  }))
  const pendingUser = pendingList.results.find((item) => item.username === username)
  expect(pendingUser).toBeTruthy()

  const initialReview = await expectOk(await request.post(
    `/api/v1/admin/onboarding/${pendingUser.id}/review/`,
    {
      headers: adminHeaders,
      data: { action: 'approve', remark: 'Playwright initial review' }
    }
  ))
  expect(initialReview.next_stage).toBe('ACTIVE')
  expect(initialReview.merchant_status).toBe('ACTIVE')
  expect(initialReview.merchant_kyc_status).toBe('APPROVED')
  expect(initialReview.merchant_no).toBeTruthy()

  const profile = await expectOk(await request.get('/api/v1/user/profile/me/', {
    headers: { Authorization: `Bearer ${customerToken}` }
  }))
  expect(profile.activation_stage).toBe('ACTIVE')
  expect(profile.remittance_eligibility.eligible).toBe(true)

  const quote = await expectOk(await request.post('/api/v1/user/payments/quote/', {
    headers: { Authorization: `Bearer ${customerToken}` },
    data: {
      amount: '100',
      from_currency: 'USD',
      to_currency: 'USD',
      fee_bearing: 'OUR'
    }
  }))
  expect(quote.quote_id).toBeTruthy()
  expect(quote.sender_total).not.toBe(quote.settle_amount)

  const order = await expectOk(await request.post('/api/v1/user/payments/apply/', {
    headers: {
      Authorization: `Bearer ${customerToken}`,
      'Idempotency-Key': `e2e-${suffix}`
    },
    data: {
      quote_id: quote.quote_id,
      beneficiary_name: 'E2E Supplier',
      beneficiary_bank: 'Supplier Bank',
      beneficiary_account: `998${suffix}`,
      beneficiary_swift: 'TESTUS33',
      beneficiary_address: '2 Supplier Street',
      remittance_purpose: 'E2E invoice'
    }
  }))
  expect(order.status).toBe('PENDING_REVIEW')
  expect(order.sender_total_amount).toBe(quote.sender_total)

  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
  }, { token: customerToken, user: registration.user })
  await page.goto('http://127.0.0.1:1030/orders')
  await expect(page.getByText(order.order_no)).toBeVisible()
})
