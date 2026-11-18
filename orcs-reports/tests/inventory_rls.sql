begin;
select set_config('test.user_a',gen_random_uuid()::text,true),set_config('test.user_b',gen_random_uuid()::text,true),set_config('test.user_c',gen_random_uuid()::text,true);
insert into auth.users(id,email) values(current_setting('test.user_a')::uuid,'inventory-a@example.invalid'),(current_setting('test.user_b')::uuid,'inventory-b@example.invalid'),(current_setting('test.user_c')::uuid,'inventory-c@example.invalid');
insert into public.orcs_sst_members(user_id) values(current_setting('test.user_a')::uuid),(current_setting('test.user_b')::uuid);
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('test.user_a'),true);
do $$ declare a jsonb; b jsonb; d jsonb:='{"product":"BURSTER ASSY","serial":"192582999991","status":"Available","active_cn":"G12345","notes":""}'; rid uuid:=gen_random_uuid(); begin
 a:=public.orcs_inventory_action('add',d,rid);
 if a->>'owner_id'<>auth.uid()::text then raise exception 'wrong owner';end if;
 b:=public.orcs_inventory_action('add',d,rid);
 if a<>b then raise exception 'not idempotent';end if;
 begin perform public.orcs_inventory_action('add',d,gen_random_uuid());raise exception 'duplicate accepted';exception when unique_violation then null;end;
 begin perform public.orcs_inventory_action('add',d||'{"serial":"bad"}',gen_random_uuid());raise exception 'bad serial accepted';exception when check_violation then null;end;
 begin perform public.orcs_inventory_action('install',jsonb_build_object('id',a->>'id','revision',1),gen_random_uuid());raise exception 'missing call accepted';exception when invalid_parameter_value then null;end;
 b:=public.orcs_inventory_action('install',jsonb_build_object('id',a->>'id','revision',1,'call_ref','TEST-CALL','rdl','12345'),gen_random_uuid());
 if b->>'status'<>'Installed' or (b->>'revision')::int<>2 then raise exception 'bad installation';end if;
 begin perform public.orcs_inventory_action('uninstall',jsonb_build_object('id',a->>'id','revision',1,'call_ref','TEST-CALL','rdl','12345'),gen_random_uuid());raise exception 'stale revision accepted';exception when serialization_failure then null;end;
 b:=public.orcs_inventory_action('uninstall',jsonb_build_object('id',a->>'id','revision',2,'call_ref','TEST-CALL','rdl','12345'),gen_random_uuid());
 b:=public.orcs_inventory_action('return',jsonb_build_object('id',a->>'id','revision',3),gen_random_uuid());
 b:=public.orcs_inventory_action('restock',jsonb_build_object('id',a->>'id','revision',4),gen_random_uuid());
 if b->>'status'<>'Available' then raise exception 'restock failed';end if;
 if (select count(*) from public.orcs_inventory_events)<>5 then raise exception 'audit trail failed';end if;
 perform set_config('test.item_id',a->>'id',true);
 begin update public.orcs_inventory_items set status='Returned';raise exception 'direct write accepted';exception when insufficient_privilege then null;end;
end $$;
select set_config('request.jwt.claim.sub',current_setting('test.user_b'),true);
do $$ begin
 if exists(select 1 from public.orcs_inventory_items) or exists(select 1 from public.orcs_inventory_events) then raise exception 'other inventory visible';end if;
 begin perform public.orcs_inventory_action('return',jsonb_build_object('id',current_setting('test.item_id'),'revision',5),gen_random_uuid());raise exception 'other owner update accepted';exception when insufficient_privilege then null;end;
end $$;
select set_config('request.jwt.claim.sub',current_setting('test.user_c'),true);
do $$ begin
 begin perform public.orcs_inventory_action('add','{"product":"PIN PAD","serial":"P9999991","status":"Available"}',gen_random_uuid());raise exception 'unapproved user accepted';exception when insufficient_privilege then null;end;
end $$;
set local role anon;
do $$ begin
 begin perform count(*) from public.orcs_inventory_items;raise exception 'anonymous read allowed';exception when insufficient_privilege then null;end;
 begin perform public.orcs_inventory_action('add','{}',gen_random_uuid());raise exception 'anonymous write allowed';exception when insufficient_privilege then null;end;
end $$;
rollback;
select 'PASS: serial validation, duplicates, idempotency, lifecycle, revision conflict, audit, ownership and anonymous denial; test data rolled back' as verification;
