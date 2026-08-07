alter table user_profiles
  add column if not exists tos_accepted_version text,
  add column if not exists tos_accepted_at timestamptz;
