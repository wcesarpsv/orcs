begin;
select set_config('test.admin',gen_random_uuid()::text,true),set_config('test.tech',gen_random_uuid()::text,true);
insert into auth.users(id,email) values(current_setting('test.admin')::uuid,'admin-verify@example.invalid'),(current_setting('test.tech')::uuid,'tech-verify@example.invalid');
insert into public.orcs_sst_members(user_id,account_role) values(current_setting('test.admin')::uuid,'admin'),(current_setting('test.tech')::uuid,'technician');
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('test.admin'),true);
do $$ begin
 perform public.orcs_manage_users('list');
 begin perform public.orcs_manage_users('status',current_setting('test.tech')::uuid,null,false);raise exception 'Admin could block';exception when insufficient_privilege then null;end;
 begin perform public.orcs_manage_users('role',current_setting('test.tech')::uuid,'admin');raise exception 'Admin could edit roles';exception when insufficient_privilege then null;end;
 begin perform public.orcs_provision_user(auth.uid(),current_setting('test.tech')::uuid,'admin');raise exception 'Provision service exposed';exception when insufficient_privilege then null;end;
end $$;
select set_config('request.jwt.claim.sub',current_setting('test.tech'),true);
do $$ begin
 begin perform public.orcs_manage_users('list');raise exception 'Technician could list';exception when insufficient_privilege then null;end;
 begin update public.orcs_sst_members set account_role='admin' where user_id=auth.uid();raise exception 'Self escalation allowed';exception when insufficient_privilege then null;end;
end $$;
reset role;
select set_config('test.owner',(select user_id::text from public.orcs_sst_members where account_role='owner'),true);
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('test.owner'),true);
select public.orcs_manage_users('status',current_setting('test.tech')::uuid,null,false);
do $$ begin
 begin perform public.orcs_manage_users('status',auth.uid(),null,false);raise exception 'Owner could be blocked';exception when insufficient_privilege then null;end;
end $$;
select set_config('request.jwt.claim.sub',current_setting('test.tech'),true);
do $$ begin
 begin perform public.orcs_manage_users('me');raise exception 'Blocked session allowed';exception when insufficient_privilege then null;end;
 begin perform public.orcs_inventory_action('add','{"product":"PIN PAD","serial":"P9999999","status":"Available"}',gen_random_uuid());raise exception 'Blocked inventory write allowed';exception when insufficient_privilege then null;end;
 if exists(select 1 from public.orcs_report_templates) then raise exception 'Blocked template access';end if;
end $$;
select set_config('request.jwt.claim.sub',current_setting('test.owner'),true);
select public.orcs_manage_users('status',current_setting('test.tech')::uuid,null,true);
select public.orcs_manage_users('role',current_setting('test.tech')::uuid,'admin');
select set_config('request.jwt.claim.sub',current_setting('test.tech'),true);
do $$ begin if public.orcs_manage_users('me')->>'role'<>'admin' then raise exception 'Owner role update failed';end if;end $$;
rollback;
select 'PASS: admin invitation authority, owner-only block/unblock and role editing, protected owner, denied escalation, blocked sessions and data; fixtures rolled back' as verification;
