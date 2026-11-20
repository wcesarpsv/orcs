alter table public.orcs_sst_members add column account_role text not null default 'technician' check(account_role in ('owner','admin','technician'));
create unique index orcs_single_owner on public.orcs_sst_members(account_role) where account_role='owner';
-- Resolve the already approved project owner by the email explicitly supplied for ORCS Reports.
update public.orcs_sst_members m set account_role='owner' from auth.users u where m.user_id=u.id and lower(u.email)='wagner@orcomputer.ca';
do $$ begin if (select count(*) from public.orcs_sst_members where account_role='owner' and active)<>1 then raise exception 'Expected one active ORCS owner'; end if; end $$;
create table public.orcs_user_audit (
 id uuid primary key default gen_random_uuid(),actor_id uuid not null references auth.users(id),target_id uuid not null references auth.users(id),
 action text not null,details jsonb not null,created_at timestamptz not null default now()
);
create index orcs_user_audit_actor_idx on public.orcs_user_audit(actor_id);
create index orcs_user_audit_target_idx on public.orcs_user_audit(target_id);
alter table public.orcs_user_audit enable row level security;
revoke all on public.orcs_user_audit from public,anon,authenticated;
create function orcs_private.manage_users(p_action text,p_target uuid default null,p_role text default null,p_active boolean default null)
returns jsonb language plpgsql security definer set search_path='' as $$
declare actor public.orcs_sst_members; target public.orcs_sst_members; output jsonb;
begin
 select * into actor from public.orcs_sst_members where user_id=auth.uid() for share;
 if not found or not actor.active then raise exception 'Approved active account required' using errcode='42501'; end if;
 if p_action='me' then return jsonb_build_object('id',actor.user_id,'role',actor.account_role,'active',actor.active); end if;
 if actor.account_role not in ('owner','admin') then raise exception 'Administrator access required' using errcode='42501'; end if;
 if p_action='list' then
  select coalesce(jsonb_agg(jsonb_build_object('id',m.user_id,'email',u.email,'name',coalesce(u.raw_user_meta_data->>'display_name',''),'role',m.account_role,'active',m.active,'invited_at',u.invited_at,'confirmed',u.email_confirmed_at is not null) order by u.email),'[]'::jsonb) into output from public.orcs_sst_members m join auth.users u on u.id=m.user_id;
  return output;
 end if;
 if actor.account_role<>'owner' then raise exception 'Only the owner can change roles or block and unblock users' using errcode='42501'; end if;
 select * into target from public.orcs_sst_members where user_id=p_target for update;
 if not found or target.account_role='owner' then raise exception 'The owner account is protected' using errcode='42501'; end if;
 if p_action='status' and p_active is not null then
  update public.orcs_sst_members set active=p_active where user_id=p_target;
 elsif p_action='role' and p_role in ('admin','technician') then
  update public.orcs_sst_members set account_role=p_role where user_id=p_target;
 else raise exception 'Invalid user action' using errcode='22023'; end if;
 insert into public.orcs_user_audit(actor_id,target_id,action,details) values(actor.user_id,p_target,p_action,jsonb_build_object('old_role',target.account_role,'old_active',target.active,'new_role',p_role,'new_active',p_active));
 return jsonb_build_object('ok',true);
end $$;
revoke all on function orcs_private.manage_users(text,uuid,text,boolean) from public,anon;
grant execute on function orcs_private.manage_users(text,uuid,text,boolean) to authenticated;
create function public.orcs_manage_users(p_action text,p_target uuid default null,p_role text default null,p_active boolean default null)
returns jsonb language sql security invoker set search_path='' as $$ select orcs_private.manage_users(p_action,p_target,p_role,p_active); $$;
revoke all on function public.orcs_manage_users(text,uuid,text,boolean) from public,anon;
grant execute on function public.orcs_manage_users(text,uuid,text,boolean) to authenticated;
-- Only the authenticated Edge Function service can provision a newly invited account.
create function orcs_private.provision_user(p_actor uuid,p_target uuid,p_role text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare actor public.orcs_sst_members;
begin
 select * into actor from public.orcs_sst_members where user_id=p_actor for share;
 if not found or not actor.active or actor.account_role not in ('owner','admin') then raise exception 'Administrator access required' using errcode='42501';end if;
 if p_role not in ('admin','technician') or p_role is null then raise exception 'Invalid account role' using errcode='22023';end if;
 if exists(select 1 from public.orcs_sst_members where user_id=p_target) then raise exception 'This account already has access. Only the owner can change existing accounts.' using errcode='22023';end if;
 insert into public.orcs_sst_members(user_id,active,account_role) values(p_target,true,p_role);
 insert into public.orcs_user_audit(actor_id,target_id,action,details) values(p_actor,p_target,'invite',jsonb_build_object('role',p_role));
 return jsonb_build_object('ok',true);
end $$;
revoke all on function orcs_private.provision_user(uuid,uuid,text) from public,anon,authenticated;
grant usage on schema orcs_private to service_role;
grant execute on function orcs_private.provision_user(uuid,uuid,text) to service_role;
create function public.orcs_provision_user(p_actor uuid,p_target uuid,p_role text)
returns jsonb language sql security invoker set search_path='' as $$ select orcs_private.provision_user(p_actor,p_target,p_role); $$;
revoke all on function public.orcs_provision_user(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.orcs_provision_user(uuid,uuid,text) to service_role;
-- A blocked account cannot read or change its saved templates, even with an unexpired token.
alter policy "Technicians manage own report templates" on public.orcs_report_templates
using ((select auth.uid())=user_id and exists(select 1 from public.orcs_sst_members where user_id=(select auth.uid()) and active))
with check ((select auth.uid())=user_id and exists(select 1 from public.orcs_sst_members where user_id=(select auth.uid()) and active));
