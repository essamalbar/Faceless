-- B3 follow-up: track Stripe's `cancel_at_period_end` so the UI can show
-- "Cancels on YYYY-MM-DD" instead of "Renews on YYYY-MM-DD" when a user
-- has scheduled a cancellation but is still paid through the period end.
--
-- Default false — most users aren't cancelling. The
-- customer.subscription.updated webhook flips it to true when Stripe says so,
-- and customer.subscription.deleted clears it when the sub actually expires.

alter table public.user_profiles
  add column cancel_at_period_end boolean not null default false;
