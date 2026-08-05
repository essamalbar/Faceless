-- A given Stripe invoice/session grants credits exactly once. A retried
-- webhook delivery then hits this unique index and is a no-op.
create unique index if not exists uq_credit_grant_ref
  on credit_transactions (reference_id, kind)
  where kind in ('subscription_renewal', 'topup');
