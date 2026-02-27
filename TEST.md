# Manual Test Guide

This document describes manual validation cases for the project.

For each case:
- **Case**: what behavior is being validated
- **Do**: the minimum action flow to execute
- **Expect**: the expected result
- **Why**: the design logic behind the expected behavior

## Pre-checks

- Start services and seed data:
  - `make up`
  - `make migrate`
  - `make seed`
- Login as an admin user.
- In the school selector, use:
  - `tc-lab` for billing/process cases
  - `reconciliation-lab` for reconciliation anomaly checks

---

## TC-Lab Billing Cases

Open `Configuration > Students`, search by `TC-XX`, then open the student dashboard (billing/payments views as needed).

### TC-01 `TC01 FullPaymentOnTime`
- **Case**: Full payment before due date closes debt cleanly.
- **Do**: Open invoice, pay full pending amount.
- **Expect**: Charges become paid, invoice closes, no residual/unpaid carry.
- **Why**: Full settlement means no allocation ambiguity and no remaining liability.

### TC-02 `TC02 FullPaymentMultipleCharges`
- **Case**: Full payment covers multiple positive charges.
- **Do**: Pay full invoice total on a multi-line invoice.
- **Expect**: All positive charges paid, invoice closed.
- **Why**: Allocation processes all debt lines when total funds are sufficient.

### TC-03 `TC03 NoPaymentInvoiceStaysOpen`
- **Case**: No payment preserves open debt.
- **Do**: Do not register any payment.
- **Expect**: Invoice remains open and charges remain unpaid.
- **Why**: State only transitions on explicit payment/allocation events.

### TC-04 `TC04 SimplePartialPayment`
- **Case**: Partial payment leaves remaining debt.
- **Do**: Pay less than total invoice amount.
- **Expect**: Invoice closes; source charge stays unpaid; a negative carry credit is created for the unallocatable amount.
- **Why**: This design avoids splitting charges and keeps allocation deterministic: only fully coverable lines are paid in-cycle, and remainder is preserved as credit for next invoice.

### TC-05 `TC05 PartialAcrossMultipleCharges`
- **Case**: Partial funds are allocated deterministically across several charges.
- **Do**: Pay amount insufficient to clear all lines (more than 100)
- **Expect**: Earlier-priority fully coverable charges are paid; cutoff and later charges stay unpaid; leftover remainder becomes negative carry credit; invoice closes.
- **Why**: Allocation uses full-line settlement only. Unallocatable remainder is stored as credit instead of splitting debt rows.

### TC-06 `TC06 PartialExactBoundary`
- **Case**: Payment ends exactly at a charge boundary.
- **Do**: Pay amount equal to sum of first N prioritized charges.
- **Expect**: Those charges are paid, later charges remain unpaid, no carry credit is created, and invoice closes.
- **Why**: Exact-boundary settlement consumes payment with zero remainder. With no unallocatable amount, no carry credit is needed.

### TC-07 `TC07 OverdueFeeGeneratesInterest`
- **Case**: Overdue fee generates interest on invoice generation.
- **Do**: Trigger manual invoice generation for the student.
- **Expect**: New interest charge appears for overdue fee debt.
- **Why**: Interest applies to overdue fee principal to model time cost of unpaid debt.

### TC-08 `TC08 InterestDeltaOnSecondGeneration`
- **Case**: Repeated generation creates only delta interest, not duplicates.
- **Do**: Trigger generation twice over same overdue base condition.
- **Expect**: Second run adds only additional delta interest; prior interest is respected.
- **Why**: Prevents double counting while still accruing over time.

### TC-09 `TC09 NoInterestOnInterestCharge`
- **Case**: Interest does not compound on interest charges.
- **Do**: Trigger generation when only interest debt is overdue.
- **Expect**: No extra interest generated from interest-origin debt.
- **Why**: Business rule: interest accrues only on fee charges.

### TC-10 `TC10 PaidFeeUnpaidInterestNoCompound`
- **Case**: Paid fee with unpaid interest still should not compound interest-on-interest.
- **Do**: Inspect scenario and run generation.
- **Expect**: Unpaid interest remains debt; no new compounded interest from it.
- **Why**: Keeps debt model transparent and avoids exponential growth artifacts.

### TC-11 `TC11 OverpaymentCreatesNegativeCarry`
- **Case**: Overpayment is preserved as a credit.
- **Do**: Pay above invoice total.
- **Expect**: Invoice closes; system records negative carry charge for future application.
- **Why**: Money received must remain auditable and reusable in next billing cycle.

### TC-12 `TC12 NegativeChargeReducesPayment`
- **Case**: Existing negative charges reduce required cash payment.
- **Do**: Pay invoice in presence of negative charge.
- **Expect**: Effective required payment is reduced; settlement considers credit + payment.
- **Why**: Credits are part of available funds for allocation.

### TC-13 `TC13 OverdueInvoicePaymentCreatesCredit`
- **Case**: Payment on overdue invoice path is controlled.
- **Do**: Attempt payment against overdue open invoice.
- **Expect**: Normal allocation is blocked; incoming money is tracked as negative credit charge.
- **Why**: Overdue handling is explicit and safer than silently mixing late cash into stale allocation.

### TC-14 `TC14 InvoiceGeneratedTwiceSamePeriod`
- **Case**: Consecutive generation in same period does not corrupt lifecycle.
- **Do**: Trigger invoice generation twice without meaningful state change.
- **Expect**: Prior open invoice closes and new invoice reflects current charges consistently.
- **Why**: Generation is modeled as a controlled rollover process.

### TC-15 `TC15 InvoiceTwiceWithNewCharge`
- **Case**: New debt between generations is reflected correctly.
- **Do**: Generate invoice, add new charge, generate again.
- **Expect**: Second invoice includes new debt snapshot; historical invoice remains stable.
- **Why**: Invoice items snapshot state at issuance for auditability.

---

## Reconciliation Lab Cases

Switch to `reconciliation-lab`, then run reconciliation from Dashboard (`Run Reconciliation`) or `Configuration > Reconciliation`.

### RECON-01 `RECON-01 Mismatch`
- **Case**: Invoice total mismatch vs invoice items.
- **Do**: Run reconciliation and open latest run detail.
- **Expect**: Finding type `invoice_total_mismatch`.
- **Why**: Detects document generation/data integrity bugs.

### RECON-02 `RECON-02 InterestOrigin`
- **Case**: Interest charge with invalid origin reference.
- **Do**: Run reconciliation and inspect findings.
- **Expect**: Finding type `interest_invalid_origin`.
- **Why**: Interest must trace to a valid source charge for auditability.

### RECON-03 `RECON-03 OpenPaid`
- **Case**: Open invoice already covered by payments.
- **Do**: Run reconciliation.
- **Expect**: Finding type `invoice_open_with_sufficient_payments`.
- **Why**: Flags missed closure transition in payment flow.

### RECON-04 `RECON-04 DuplicatePayment`
- **Case**: Duplicate payment pattern in short window.
- **Do**: Run reconciliation.
- **Expect**: Finding type `duplicate_payment_window`.
- **Why**: Detects likely double-submit/retry anomalies.

### RECON-06 `RECON-06 SchoolBalanceDrift`
- **Case**: School-level totals violate ledger identity.
- **Do**: Run reconciliation and inspect latest findings.
- **Expect**: Finding type `school_balance_equation_mismatch`.
- **Why**: Global invariant check ensures `total_charged - total_paid - total_pending = 0` and flags accounting drift.

---

## Dashboard Financial Summary Checks

On `tc-lab` dashboard:
- **Do**: Open home dashboard as admin.
- **Expect**:
  - Summary metrics visible (`total_billed_amount`, `total_charged_amount`, `total_paid_amount`, `total_pending_amount`, `student_count`)
  - `Relevant invoices` buckets visible:
    - `Overdue 90+ days`
    - `Top pending open`
    - `Due in next 7 days`
- **Why**: These buckets prioritize operational follow-up: risk (very overdue), impact (largest pending), and urgency (about to mature).

---

## Notes

- In this project, invoices are intentionally treated as read-only financial documents in API behavior; lifecycle changes happen through business flows (generation/payment/reconciliation), not arbitrary CRUD edits.
- If a manual result differs from expected, capture:
  - school
  - student external id
  - invoice id
  - action timestamp
  - observed vs expected result
