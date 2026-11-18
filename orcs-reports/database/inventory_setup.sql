-- Dedicated ORCS Reports project. No anonymous access; technician identity comes from auth.uid().
create table public.orcs_inventory_items (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id),
 serial text not null unique,
 product text not null,
 active_cn text not null default '' check(active_cn='' or active_cn ~ '^([GS][0-9]{5}|L[0-9]{6})$'),
 status text not null check(status in ('Available','Installed','Return pending','Returned')),
 notes text not null default '' check(length(notes)<=2000),
 call_ref text not null default '' check(length(call_ref)<=100),
 rdl text not null default '' check(rdl='' or rdl ~ '^[0-9]{1,10}$'),
 revision integer not null default 1 check(revision>0),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 constraint orcs_inventory_serial_format check (
 (product='PIN PAD' and serial ~ '^P[0-9]{7}$') or
 (product='PRINTER VKP80III' and serial ~ '^MEC[0-9]{13}$') or
 (product in ('19INCH CARMANAH SIGN','30INCH CARMANAH SIGN','30INCH NEW CARMANAH SIGN') and serial ~ '^EMONJC[0-9]{6}$') or
 (product='4.5 INCH BETSLIP RDR' and serial ~ '^800000[0-9]{10}$') or
 (product in ('BURSTER ASSY','QUAD BURSTER ASSY') and serial ~ '^192582[0-9]{6}$') or
 (product='DS4608 SCANNER -BLACK' and serial ~ '^[0-9]{14}$') or
 (product='MAINBOARD ENCLOSURE' and serial ~ '^[0-9A-F]{16}$'))
);
create index orcs_inventory_owner_idx on public.orcs_inventory_items(owner_id,status,updated_at desc);
create table public.orcs_inventory_events (
 id uuid primary key default gen_random_uuid(), item_id uuid not null references public.orcs_inventory_items(id),
 owner_id uuid not null references auth.users(id), request_id uuid not null unique,
 action text not null, payload jsonb not null, snapshot jsonb not null,
 created_at timestamptz not null default now()
);
create index orcs_inventory_events_owner_idx on public.orcs_inventory_events(owner_id,created_at desc);
create index orcs_inventory_events_item_idx on public.orcs_inventory_events(item_id,created_at desc);
alter table public.orcs_inventory_items enable row level security;
alter table public.orcs_inventory_events enable row level security;
revoke all on public.orcs_inventory_items,public.orcs_inventory_events from public,anon,authenticated;
grant select on public.orcs_inventory_items,public.orcs_inventory_events to authenticated;
create policy inventory_owner_read on public.orcs_inventory_items for select to authenticated using (owner_id=(select auth.uid()) and exists(select 1 from public.orcs_sst_members where user_id=(select auth.uid()) and active));
create policy inventory_events_owner_read on public.orcs_inventory_events for select to authenticated using (owner_id=(select auth.uid()) and exists(select 1 from public.orcs_sst_members where user_id=(select auth.uid()) and active));
create function orcs_private.inventory_action(p_action text,p_data jsonb,p_request_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); item public.orcs_inventory_items; previous public.orcs_inventory_events; new_status text; sid text;
begin
 if uid is null or not exists(select 1 from public.orcs_sst_members where user_id=uid and active) then raise exception 'Approved technician access required' using errcode='42501'; end if;
 if p_request_id is null or jsonb_typeof(p_data) is distinct from 'object' or p_action not in ('add','install','uninstall','return','restock') or p_action is null then raise exception 'Invalid inventory request'; end if;
 perform pg_advisory_xact_lock(hashtextextended('inventory-request:'||p_request_id::text,0));
 select * into previous from public.orcs_inventory_events where request_id=p_request_id;
 if found then
  if previous.owner_id<>uid or previous.action<>p_action or previous.payload<>p_data then raise exception 'Request already used' using errcode='22023'; end if;
  return previous.snapshot;
 end if;
 if p_action='add' then
  sid:=p_data->>'serial';
  if sid is null or p_data->>'status' not in ('Available','Return pending') or p_data->>'status' is null then raise exception 'Invalid new inventory item' using errcode='22023'; end if;
  perform pg_advisory_xact_lock(hashtextextended('inventory-serial:'||sid,0));
  if exists(select 1 from public.orcs_inventory_items where serial=sid) then raise exception 'Serial already registered. Use its existing record.' using errcode='23505'; end if;
  insert into public.orcs_inventory_items(owner_id,serial,product,active_cn,status,notes) values(uid,sid,p_data->>'product',coalesce(p_data->>'active_cn',''),p_data->>'status',coalesce(p_data->>'notes','')) returning * into item;
 else
  select * into item from public.orcs_inventory_items where id=(p_data->>'id')::uuid and owner_id=uid for update;
  if not found then raise exception 'Inventory item unavailable' using errcode='42501'; end if;
  if (p_data->>'revision')::integer is distinct from item.revision then raise exception 'revision_conflict' using errcode='40001'; end if;
  new_status:=case when p_action='install' and item.status='Available' then 'Installed'
    when p_action='uninstall' and item.status='Installed' then 'Return pending'
    when p_action='return' and item.status in ('Available','Return pending') then 'Returned'
    when p_action='restock' and item.status='Returned' then 'Available' else null end;
  if new_status is null then raise exception 'Invalid status transition' using errcode='22023'; end if;
  if p_action in ('install','uninstall') and (coalesce(p_data->>'call_ref','')='' or coalesce(p_data->>'rdl','') !~ '^[0-9]{1,10}$') then raise exception 'Call reference and valid RDL required' using errcode='22023'; end if;
  update public.orcs_inventory_items set status=new_status,revision=revision+1,updated_at=now(),call_ref=case when p_action in ('install','uninstall') then p_data->>'call_ref' else call_ref end,rdl=case when p_action in ('install','uninstall') then p_data->>'rdl' else rdl end where id=item.id returning * into item;
 end if;
 insert into public.orcs_inventory_events(item_id,owner_id,request_id,action,payload,snapshot) values(item.id,uid,p_request_id,p_action,p_data,to_jsonb(item));
 return to_jsonb(item);
end $$;
revoke all on function orcs_private.inventory_action(text,jsonb,uuid) from public,anon;
grant execute on function orcs_private.inventory_action(text,jsonb,uuid) to authenticated;
create function public.orcs_inventory_action(p_action text,p_data jsonb,p_request_id uuid)
returns jsonb language sql security invoker set search_path='' as $$ select orcs_private.inventory_action(p_action,p_data,p_request_id); $$;
revoke all on function public.orcs_inventory_action(text,jsonb,uuid) from public,anon;
grant execute on function public.orcs_inventory_action(text,jsonb,uuid) to authenticated;
