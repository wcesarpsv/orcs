-- Apply only to the Supabase project selected for ORCS Reports.
create schema if not exists orcs_private;
revoke all on schema orcs_private from public, anon;
create table if not exists public.orcs_sst_members (
  user_id uuid primary key references auth.users(id),
  active boolean not null default true
);
create table if not exists public.orcs_sst_pm_visits (
  id uuid primary key default gen_random_uuid(),
  sst_id text not null check (sst_id ~ '^[0-9]{6}$'),
  revision integer not null check (revision > 0),
  record jsonb not null check (jsonb_typeof(record)='object'),
  request_id uuid not null unique,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  unique(sst_id,revision)
);
alter table public.orcs_sst_members enable row level security;
alter table public.orcs_sst_pm_visits enable row level security;
revoke all on public.orcs_sst_members, public.orcs_sst_pm_visits from anon, authenticated;
grant select on public.orcs_sst_members, public.orcs_sst_pm_visits to authenticated;
create policy orcs_member_self on public.orcs_sst_members for select to authenticated using (user_id=(select auth.uid()));
create policy orcs_approved_technicians_read on public.orcs_sst_pm_visits for select to authenticated using (exists(select 1 from public.orcs_sst_members m where m.user_id=(select auth.uid()) and m.active));
create or replace view public.orcs_sst_assets with (security_invoker=true) as
select distinct on (sst_id) sst_id,revision,record,created_at as updated_at from public.orcs_sst_pm_visits order by sst_id,revision desc;
revoke all on public.orcs_sst_assets from anon;
grant select on public.orcs_sst_assets to authenticated;
create or replace function orcs_private.save_sst_pm(p_record jsonb,p_expected_revision integer,p_request_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); sid text:=p_record->>'sst_id'; current_revision integer; existing public.orcs_sst_pm_visits; inserted public.orcs_sst_pm_visits;
begin
 if uid is null or not exists(select 1 from public.orcs_sst_members where user_id=uid and active) then raise exception 'Approved technician access required' using errcode='42501'; end if;
 if sid is null or sid !~ '^[0-9]{6}$' or p_expected_revision<0 or p_expected_revision is null or p_request_id is null then raise exception 'Invalid SST save request'; end if;
 if p_record->>'completed' is distinct from 'true' or jsonb_typeof(p_record->'components') is distinct from 'array' or jsonb_array_length(p_record->'components')<>16 or p_record ? 'photos' then raise exception 'Invalid completed PM record'; end if;
 if exists(select 1 from jsonb_array_elements(p_record->'components') c where c->>'test'='Failed') then raise exception 'Resolve failed tests before saving'; end if;
 perform pg_advisory_xact_lock(hashtextextended('orcs_sst:'||sid,0));
 select * into existing from public.orcs_sst_pm_visits where request_id=p_request_id;
 if found then
   if existing.created_by<>uid or existing.sst_id<>sid or existing.record<>p_record then raise exception 'Request already used for another record'; end if;
   return jsonb_build_object('sst_id',sid,'revision',existing.revision,'visit_id',existing.id);
 end if;
 select coalesce(max(revision),0) into current_revision from public.orcs_sst_pm_visits where sst_id=sid;
 if current_revision<>p_expected_revision then raise exception 'revision_conflict'; end if;
 insert into public.orcs_sst_pm_visits(sst_id,revision,record,request_id,created_by) values(sid,current_revision+1,p_record,p_request_id,uid) returning * into inserted;
 return jsonb_build_object('sst_id',sid,'revision',inserted.revision,'visit_id',inserted.id);
end; $$;
revoke all on function orcs_private.save_sst_pm(jsonb,integer,uuid) from public,anon;
grant usage on schema orcs_private to authenticated;
grant execute on function orcs_private.save_sst_pm(jsonb,integer,uuid) to authenticated;
create or replace function public.orcs_save_sst_pm(p_record jsonb,p_expected_revision integer,p_request_id uuid)
returns jsonb language sql security invoker set search_path='' as $$ select orcs_private.save_sst_pm(p_record,p_expected_revision,p_request_id); $$;
revoke all on function public.orcs_save_sst_pm(jsonb,integer,uuid) from public,anon;
grant execute on function public.orcs_save_sst_pm(jsonb,integer,uuid) to authenticated;
-- Create technician accounts in Supabase Auth, then approve each known user UUID:
-- insert into public.orcs_sst_members(user_id) values ('<approved-auth-user-uuid>');
