-- Extend the existing personal-template catalog without changing ownership policies or saved rows.
alter table public.orcs_report_templates drop constraint orcs_report_templates_report_type_check;
alter table public.orcs_report_templates add constraint orcs_report_templates_report_type_check
check (report_type in ('INSTALLATION','SST Install','DEINSTALLATION','BREAKFIX WJS','PM'));
