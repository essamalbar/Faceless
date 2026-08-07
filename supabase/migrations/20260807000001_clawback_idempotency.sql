-- A given disputed/refunded charge claws back credits exactly once. A retried
-- charge.dispute.created / charge.refunded then hits this index and is a no-op.
create unique index if not exists uq_credit_clawback_ref
  on credit_transactions (reference_id, kind)
  where kind = 'chargeback_clawback';
