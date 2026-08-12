-- Paddle (Merchant of Record) customer id, analogous to stripe_customer_id.
-- Additive + idempotent so re-running the bundle is safe.
alter table user_profiles
  add column if not exists paddle_customer_id text;
