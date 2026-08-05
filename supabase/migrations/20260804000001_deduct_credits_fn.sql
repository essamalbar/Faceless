-- Atomic check-and-deduct: serialize per-user via an advisory lock so two
-- concurrent runs can't both pass the balance check and overspend.
create or replace function deduct_credits(
  p_user_id uuid, p_amount int, p_kind text,
  p_reference_id text, p_description text
) returns int language plpgsql as $$
declare v_balance int;
begin
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));
  select coalesce(sum(amount), 0) into v_balance
    from credit_transactions where user_id = p_user_id;
  if v_balance < p_amount then
    return -1;  -- insufficient; caller raises InsufficientCredits
  end if;
  insert into credit_transactions(user_id, amount, kind, reference_id, description)
    values (p_user_id, -p_amount, p_kind, p_reference_id, p_description);
  return v_balance - p_amount;
end $$;
