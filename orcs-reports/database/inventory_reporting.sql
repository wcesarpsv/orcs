create function orcs_private.inventory_report(p_kind text default 'inventory',p_owner uuid default null,p_status text default 'held',p_offset integer default 0)
returns jsonb language plpgsql security definer set search_path='' as $$
declare output jsonb; people jsonb; totals jsonb; n bigint; rows jsonb;
begin
 if not exists(select 1 from public.orcs_sst_members where user_id=auth.uid() and active and account_role in ('owner','admin')) then raise exception 'Active administrator access required' using errcode='42501';end if;
 if p_kind not in ('inventory','installations') or p_kind is null or p_offset is null or p_offset<0 or p_offset>1000000 or p_status not in ('held','all','Available','Installed','Return pending','Returned') then raise exception 'Invalid reporting filter' using errcode='22023';end if;
 select coalesce(jsonb_agg(jsonb_build_object('id',m.user_id,'name',coalesce(nullif(u.raw_user_meta_data->>'display_name',''),u.email),'email',u.email,'active',m.active,'installation_events',(select count(*) from public.orcs_inventory_events where owner_id=m.user_id and action='install')+(select count(*) from public.orcs_sst_kit_events where actor_id=m.user_id and action='component_used'),'available',(select count(*) from public.orcs_inventory_items where owner_id=m.user_id and status='Available'),'return_pending',(select count(*) from public.orcs_inventory_items where owner_id=m.user_id and status='Return pending'),'installed',(select count(*) from public.orcs_inventory_items where owner_id=m.user_id and status='Installed'),'returned',(select count(*) from public.orcs_inventory_items where owner_id=m.user_id and status='Returned')) order by u.email),'[]'::jsonb) into people from public.orcs_sst_members m join auth.users u on u.id=m.user_id;
 select jsonb_build_object('available',count(*) filter(where status='Available'),'return_pending',count(*) filter(where status='Return pending'),'installed',count(*) filter(where status='Installed'),'returned',count(*) filter(where status='Returned')) into totals from public.orcs_inventory_items where p_owner is null or owner_id=p_owner;
 if p_kind='inventory' then
  select count(*) into n from public.orcs_inventory_items i where (p_owner is null or i.owner_id=p_owner) and (p_status='all' or p_status='held' and i.status in ('Available','Return pending') or i.status=p_status);
  select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) into rows from (select i.id,i.owner_id,coalesce(nullif(u.raw_user_meta_data->>'display_name',''),u.email) as technician,u.email,i.product,i.serial,i.active_cn,i.status,i.call_ref,i.rdl,i.updated_at from public.orcs_inventory_items i join auth.users u on u.id=i.owner_id where (p_owner is null or i.owner_id=p_owner) and (p_status='all' or p_status='held' and i.status in ('Available','Return pending') or i.status=p_status) order by u.email,i.product,i.serial limit 200 offset p_offset) t;
 else
  with events as (
    select e.id::text as id,e.owner_id as technician_id,e.created_at,e.snapshot->>'product' as product,e.snapshot->>'serial' as serial,e.snapshot->>'call_ref' as call_ref,e.snapshot->>'rdl' as rdl,'My Inventory'::text as source,i.status as current_status from public.orcs_inventory_events e left join public.orcs_inventory_items i on i.id=e.item_id where e.action='install'
    union all
    select e.id::text,e.actor_id,e.created_at,e.details->>'product',e.details->>'serial',e.details->>'call_ref',e.details->>'rdl','SST Kit',null::text from public.orcs_sst_kit_events e where e.action='component_used'
  ) select count(*) into n from events where p_owner is null or technician_id=p_owner;
  with events as (
    select e.id::text as id,e.owner_id as technician_id,e.created_at,e.snapshot->>'product' as product,e.snapshot->>'serial' as serial,e.snapshot->>'call_ref' as call_ref,e.snapshot->>'rdl' as rdl,'My Inventory'::text as source,i.status as current_status from public.orcs_inventory_events e left join public.orcs_inventory_items i on i.id=e.item_id where e.action='install'
    union all
    select e.id::text,e.actor_id,e.created_at,e.details->>'product',e.details->>'serial',e.details->>'call_ref',e.details->>'rdl','SST Kit',null::text from public.orcs_sst_kit_events e where e.action='component_used'
  ) select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) into rows from (select e.*,coalesce(nullif(u.raw_user_meta_data->>'display_name',''),u.email) as technician,u.email from events e join auth.users u on u.id=e.technician_id where p_owner is null or e.technician_id=p_owner order by e.created_at desc,e.id limit 200 offset p_offset) t;
 end if;
 return jsonb_build_object('technicians',people,'totals',totals,'rows',rows,'count',n,'next_offset',case when p_offset+200<n then p_offset+200 else null end,'generated_at',now());
end $$;
revoke all on function orcs_private.inventory_report(text,uuid,text,integer) from public,anon;
grant execute on function orcs_private.inventory_report(text,uuid,text,integer) to authenticated;
create function public.orcs_inventory_report(p_kind text default 'inventory',p_owner uuid default null,p_status text default 'held',p_offset integer default 0)
returns jsonb language sql security invoker set search_path='' as $$ select orcs_private.inventory_report(p_kind,p_owner,p_status,p_offset); $$;
revoke all on function public.orcs_inventory_report(text,uuid,text,integer) from public,anon;
grant execute on function public.orcs_inventory_report(text,uuid,text,integer) to authenticated;
