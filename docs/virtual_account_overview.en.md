# Virtual Account (VA) — Feature Overview

## 1. Definition

A Virtual Account (VA) is a dedicated **virtual receiving identifier** generated under a bank / payment institution's physical "umbrella master account". It enables low-cost localized collection, automatic fund aggregation and precise reconciliation. It is **not a physical bank card and not a standalone deposit account**.

Underlying logic: under the licensed institution's physical master account (NostroAccount), the system maps and generates multiple independent virtual sub-accounts. A "book-entry separation" mechanism decouples the fund flow from the information flow, completing cross-border collection through low-cost local clearing networks.

Two forms:

- **VLA (Virtual Ledger Account)**: pure internal ledger record, with no external bank-account form.
- **VAV (Virtual Bank Account Number)**: presents a seemingly real bank account (with local routing code / IBAN); the mainstream form for cross-border collection.

## 2. Core Capabilities

- **Localized collection**: Provide local bank receiving details (account number, Routing Number / IBAN) for target markets (US / EU / UK / HK / SG …). Payers transfer via low-cost local clearing networks such as ACH or SEPA instead of expensive international wires.
- **Automatic aggregation**: Funds flowing into each virtual sub-account are automatically swept into the licensed institution's single physical master account, unifying multi-currency, multi-source balances.
- **Smart auto-reconciliation**: Each VA is bound to a specific customer, order or business scenario. The system identifies the payer and matches the transaction by the unique VA number — no manual reference matching needed.
- **Multi-currency**: Issue VA profiles in USD / EUR / GBP and more, enabling per-currency aggregation and later FX or withdrawal.
- **Compliance & risk isolation**: As a sub-identifier under the umbrella account, the VA never exposes the real master account number, reducing data-leak risk and facilitating AML monitoring.

## 3. Key Characteristics

- **Essential difference**: A VA is a set of "receiving details" (account number, bank code, etc.). It cannot be used for card spending, has no CVV, and is receive-only — distinct from a spendable Virtual Card.
- **How it works**: Funds actually enter the payment institution's real master account. The VA number is only a bookkeeping tag used to attribute ownership; it cannot be used for direct cash withdrawal.

## 4. Use Cases

- Cross-border e-commerce payouts
- B2B trade collection
- SaaS subscription billing
- Multi-subsidiary / multi-order financial split

## 5. Disclaimer

Virtual Accounts are typically provided by cross-border payment institutions or banks. Supported currencies, clearing channels and withdrawal rules are subject to the service provider's terms.
