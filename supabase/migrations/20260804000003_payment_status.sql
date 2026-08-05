alter table user_profiles
  add column if not exists payment_status text not null default 'active';
