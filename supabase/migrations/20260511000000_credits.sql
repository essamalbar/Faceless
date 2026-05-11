-- B3: per-user credit ledger + Stripe customer mapping.
-- See docs/superpowers/specs/2026-05-11-stripe-credits-design.md

-- ---------------------------------------------------------------------------
-- 1. user_profiles: lightweight per-user app metadata.
-- ---------------------------------------------------------------------------
create table public.user_profiles (
  id                    uuid primary key references auth.users(id) on delete cascade,
  stripe_customer_id    text unique,
  current_plan          text not null default 'free'
                        check (current_plan in ('free','starter','creator','pro')),
  current_period_end    timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create or replace function public.touch_user_profiles_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end;
$$;
create trigger user_profiles_touch_updated_at
  before update on public.user_profiles
  for each row execute function public.touch_user_profiles_updated_at();

-- ---------------------------------------------------------------------------
-- 2. credit_transactions: append-only ledger.
--    Never UPDATE or DELETE rows. Corrections = new rows with kind='admin_adjust'.
-- ---------------------------------------------------------------------------
create table public.credit_transactions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  amount        integer not null,
                -- positive = credit, negative = debit
  kind          text not null
                check (kind in (
                  'signup_grant',
                  'subscription_renewal',
                  'topup',
                  'run_charge',
                  'run_refund',
                  'admin_adjust'
                )),
  reference_id  text,   -- run_id for run_charge/refund; stripe id for billing events
  description   text,
  created_at    timestamptz not null default now()
);
create index credit_transactions_user_id_created_at_idx
  on public.credit_transactions(user_id, created_at desc);

-- Convenience: balance = sum(amount). Used by API and tests.
create view public.user_balance as
  select user_id,
         coalesce(sum(amount), 0)::integer as balance
  from public.credit_transactions
  group by user_id;

-- ---------------------------------------------------------------------------
-- 3. Row-Level Security.
-- ---------------------------------------------------------------------------
alter table public.user_profiles      enable row level security;
alter table public.credit_transactions enable row level security;

-- Users can read their own profile + ledger. All writes go via service_role.
create policy "users read own profile" on public.user_profiles
  for select using (auth.uid() = id);

create policy "users read own transactions" on public.credit_transactions
  for select using (auth.uid() = user_id);

-- service_role bypasses RLS by default — backend writes are unrestricted.
