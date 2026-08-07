-- Tier-4C abuse & cost controls: one DB-backed rate primitive.
-- Backs (a) the daily song-approve cap (was a per-instance JSON file on
-- GCS-Fuse, racy across Cloud Run instances) and (b) the per-user hourly
-- throttle on the unmetered LLM draft/regen endpoints.
create table if not exists public.rate_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null,
  action     text not null,
  created_at timestamptz not null default now()
);

create index if not exists rate_events_lookup
  on public.rate_events (user_id, action, created_at desc);
