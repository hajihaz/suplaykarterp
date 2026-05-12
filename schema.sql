-- ============================================================
--  Suplaykart Staff — Workforce OS
--  Reference Postgres schema for Supabase
--  Project: edbvlpippapjookhwbzw
-- ------------------------------------------------------------
--  How to use:
--    1. Open Supabase → SQL editor.
--    2. Paste this whole file and Run.
--    3. Then create the required Storage buckets (see bottom).
--    4. Seed the fixed admin user (see README).
--  Idempotent: re-running is safe (CREATE TABLE IF NOT EXISTS).
-- ============================================================

create extension if not exists "pgcrypto";

-- ====================  PROFILES  ====================
-- One row per Supabase Auth user, keyed by auth.uid().
create table if not exists public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  username     text unique,
  full_name    text,
  email        text,
  phone        text,
  address      text,
  emergency    text,
  avatar_url   text,
  role         text not null default 'employee'
                 check (role in ('employee','manager','admin')),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_profiles_role on public.profiles(role);

-- ====================  EMPLOYEES  ====================
-- The HR directory. id is the human-readable SKT-### code, not auth.uid.
create table if not exists public.employees (
  id           text primary key,
  user_id      uuid references auth.users(id) on delete set null,
  name         text not null,
  role         text,
  dept         text,
  shift        text,
  mobile       text,
  email        text,
  bank         text,
  joined_on    date,
  status       text default 'Active',
  score        integer default 80,
  color        text,
  salary       integer,
  emergency    text,
  avatar_url   text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_employees_dept on public.employees(dept);
create index if not exists idx_employees_status on public.employees(status);

-- ====================  ATTENDANCE  ====================
-- One row per employee per day (the day-summary).
create table if not exists public.attendance (
  id              uuid primary key default gen_random_uuid(),
  employee_id     text not null references public.employees(id) on delete cascade,
  date            date not null,
  day             text,
  punch_in        text,
  punch_out       text,
  total_hours     text,
  status          text,
  geofence_status text,
  late_minutes    integer default 0,
  ot_minutes      integer default 0,
  deductions      integer default 0,
  session_index   integer default 1,
  created_at      timestamptz not null default now(),
  unique (employee_id, date)
);
create index if not exists idx_attendance_emp_date on public.attendance(employee_id, date desc);

-- ====================  ATTENDANCE_SESSIONS  ====================
-- The granular punch-in/punch-out events behind each attendance row.
create table if not exists public.attendance_sessions (
  id           uuid primary key default gen_random_uuid(),
  employee_id  text not null references public.employees(id) on delete cascade,
  date         date not null default current_date,
  punch_in     timestamptz not null default now(),
  punch_out    timestamptz,
  geofence_ok  boolean default true,
  lat          double precision,
  lng          double precision,
  created_at   timestamptz not null default now()
);
create index if not exists idx_att_sess_emp on public.attendance_sessions(employee_id, date desc);

-- ====================  TASKS  ====================
create table if not exists public.tasks (
  id              text primary key,
  title           text not null,
  description     text,
  assignee_id     text references public.employees(id) on delete set null,
  assignee_label  text,
  type            text default 'one-time',  -- daily | weekly | one-time
  priority        text default 'medium',    -- urgent | high | medium | low
  status          text default 'active',    -- active | completed | archived
  due             timestamptz,
  created_at      timestamptz not null default now(),
  completed_at    timestamptz,
  archived_at     timestamptz,
  created_by      uuid references auth.users(id) on delete set null
);
create index if not exists idx_tasks_assignee on public.tasks(assignee_id);
create index if not exists idx_tasks_status   on public.tasks(status);

-- ====================  ANNOUNCEMENTS  ====================
create table if not exists public.announcements (
  id           uuid primary key default gen_random_uuid(),
  title        text not null,
  message      text not null,
  audience     text,
  priority     text default 'normal',
  created_at   timestamptz not null default now(),
  created_by   uuid references auth.users(id) on delete set null
);
create index if not exists idx_announce_created on public.announcements(created_at desc);

-- ====================  SALARY_RECORDS  ====================
create table if not exists public.salary_records (
  id              text primary key,
  employee_id     text not null references public.employees(id) on delete cascade,
  employee_name   text,
  month           text not null,            -- e.g. 'May-2026'
  base            integer not null,
  incentives      integer default 0,
  deductions      integer default 0,
  net             integer not null,
  status          text default 'pending',   -- pending | paid
  paid_at         timestamptz,
  paid_by         uuid references auth.users(id) on delete set null,
  created_at      timestamptz not null default now(),
  unique (employee_id, month)
);
create index if not exists idx_salary_emp on public.salary_records(employee_id);
create index if not exists idx_salary_month on public.salary_records(month);

-- ====================  LEAVES  ====================
create table if not exists public.leaves (
  id              text primary key,
  employee_id     text not null references public.employees(id) on delete cascade,
  employee_name   text,
  type            text,        -- Sick | Casual | Permission | Resignation
  days            text,
  period          text,
  reason          text,
  severity        text,        -- red | amber | green (UI tint)
  status          text default 'pending',  -- pending | approved | rejected
  submitted_at    timestamptz not null default now(),
  resolved_by     text,
  resolved_at     timestamptz
);
create index if not exists idx_leaves_status on public.leaves(status);
create index if not exists idx_leaves_emp    on public.leaves(employee_id);

-- ====================  WARNINGS  ====================
create table if not exists public.warnings (
  id              text primary key,
  employee_id     text not null references public.employees(id) on delete cascade,
  employee_name   text,
  category        text,        -- Attendance | Performance | Dress code | Conduct
  severity        text,        -- minor | moderate | severe
  reason          text,
  issued_at       timestamptz not null default now(),
  issued_by       text,
  acknowledged    boolean default false
);
create index if not exists idx_warnings_emp on public.warnings(employee_id);

-- ====================  NOTIFICATIONS  ====================
-- recipient_id null = broadcast (visible to everyone)
create table if not exists public.notifications (
  id              uuid primary key default gen_random_uuid(),
  recipient_id    uuid references auth.users(id) on delete cascade,
  category        text,        -- attendance | leave | task | salary | security | announcement | leaderboard | resignation
  title           text not null,
  body            text,
  icon            text,
  tint            text,
  link            text,
  read            boolean default false,
  created_at      timestamptz not null default now()
);
create index if not exists idx_notifs_recipient on public.notifications(recipient_id, read);
create index if not exists idx_notifs_created   on public.notifications(created_at desc);

-- ====================  AUDIT_LOGS  ====================
create table if not exists public.audit_logs (
  id           bigserial primary key,
  action       text not null,    -- e.g. 'salary.mark_paid'
  details      text,
  actor        text,             -- human-readable name/initials
  actor_id     uuid references auth.users(id) on delete set null,
  created_at   timestamptz not null default now()
);
create index if not exists idx_audit_created on public.audit_logs(created_at desc);
create index if not exists idx_audit_action  on public.audit_logs(action);

-- ====================  TRIGGERS  ====================
-- Auto-bump updated_at on profiles and employees
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists trg_profiles_touch on public.profiles;
create trigger trg_profiles_touch
  before update on public.profiles
  for each row execute function public.touch_updated_at();

drop trigger if exists trg_employees_touch on public.employees;
create trigger trg_employees_touch
  before update on public.employees
  for each row execute function public.touch_updated_at();

-- Auto-create a profile row when a new auth user is created
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email, full_name, role)
  values (new.id,
          new.email,
          coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email,'@',1)),
          coalesce(new.raw_user_meta_data->>'role', 'employee'))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists trg_on_auth_user_created on auth.users;
create trigger trg_on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ====================  ROW LEVEL SECURITY  ====================
-- Enable RLS on every table
alter table public.profiles            enable row level security;
alter table public.employees           enable row level security;
alter table public.attendance          enable row level security;
alter table public.attendance_sessions enable row level security;
alter table public.tasks               enable row level security;
alter table public.announcements       enable row level security;
alter table public.salary_records      enable row level security;
alter table public.leaves              enable row level security;
alter table public.warnings            enable row level security;
alter table public.notifications       enable row level security;
alter table public.audit_logs          enable row level security;

-- Helper: is the current user an admin or manager?
create or replace function public.is_staff()
returns boolean language sql stable as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role in ('admin','manager')
  );
$$;
create or replace function public.is_admin()
returns boolean language sql stable as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

-- ---- Profiles ----
drop policy if exists "profiles_self_read"     on public.profiles;
drop policy if exists "profiles_staff_read"    on public.profiles;
drop policy if exists "profiles_self_upsert"   on public.profiles;
drop policy if exists "profiles_admin_write"   on public.profiles;
create policy "profiles_self_read"   on public.profiles for select using (auth.uid() = id);
create policy "profiles_staff_read"  on public.profiles for select using (public.is_staff());
create policy "profiles_self_upsert" on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);
create policy "profiles_admin_write" on public.profiles for all using (public.is_admin()) with check (public.is_admin());

-- ---- Employees ----
drop policy if exists "employees_authenticated_read" on public.employees;
drop policy if exists "employees_admin_write"        on public.employees;
create policy "employees_authenticated_read" on public.employees for select using (auth.role() = 'authenticated');
create policy "employees_admin_write"        on public.employees for all    using (public.is_admin()) with check (public.is_admin());

-- ---- Attendance + sessions ----
drop policy if exists "att_self_read"     on public.attendance;
drop policy if exists "att_staff_read"    on public.attendance;
drop policy if exists "att_self_write"    on public.attendance;
drop policy if exists "att_staff_write"   on public.attendance;
create policy "att_self_read"   on public.attendance  for select using (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "att_staff_read"  on public.attendance  for select using (public.is_staff());
create policy "att_self_write"  on public.attendance  for insert with check (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "att_staff_write" on public.attendance  for all    using (public.is_staff()) with check (public.is_staff());

drop policy if exists "att_sess_self_read"  on public.attendance_sessions;
drop policy if exists "att_sess_staff_read" on public.attendance_sessions;
drop policy if exists "att_sess_self_write" on public.attendance_sessions;
drop policy if exists "att_sess_staff_write" on public.attendance_sessions;
create policy "att_sess_self_read"  on public.attendance_sessions for select using (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "att_sess_staff_read" on public.attendance_sessions for select using (public.is_staff());
create policy "att_sess_self_write" on public.attendance_sessions for all    using (employee_id in (select id from public.employees where user_id = auth.uid())) with check (true);
create policy "att_sess_staff_write" on public.attendance_sessions for all   using (public.is_staff()) with check (public.is_staff());

-- ---- Tasks ----
drop policy if exists "tasks_assignee_read" on public.tasks;
drop policy if exists "tasks_staff_read"    on public.tasks;
drop policy if exists "tasks_assignee_status" on public.tasks;
drop policy if exists "tasks_staff_write"   on public.tasks;
create policy "tasks_assignee_read"   on public.tasks for select using (auth.role() = 'authenticated');
create policy "tasks_staff_read"      on public.tasks for select using (public.is_staff());
create policy "tasks_assignee_status" on public.tasks for update using (
  assignee_id in (select id from public.employees where user_id = auth.uid())
) with check (
  assignee_id in (select id from public.employees where user_id = auth.uid())
);
create policy "tasks_staff_write" on public.tasks for all using (public.is_staff()) with check (public.is_staff());

-- ---- Announcements ----
drop policy if exists "ann_authenticated_read" on public.announcements;
drop policy if exists "ann_staff_write"        on public.announcements;
create policy "ann_authenticated_read" on public.announcements for select using (auth.role() = 'authenticated');
create policy "ann_staff_write"        on public.announcements for all    using (public.is_staff()) with check (public.is_staff());

-- ---- Salary ----
drop policy if exists "salary_self_read"     on public.salary_records;
drop policy if exists "salary_admin_read"    on public.salary_records;
drop policy if exists "salary_admin_write"   on public.salary_records;
create policy "salary_self_read"   on public.salary_records for select using (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "salary_admin_read"  on public.salary_records for select using (public.is_staff());
create policy "salary_admin_write" on public.salary_records for all    using (public.is_admin()) with check (public.is_admin());

-- ---- Leaves ----
drop policy if exists "leaves_self_read"   on public.leaves;
drop policy if exists "leaves_staff_read"  on public.leaves;
drop policy if exists "leaves_self_insert" on public.leaves;
drop policy if exists "leaves_staff_write" on public.leaves;
create policy "leaves_self_read"   on public.leaves for select using (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "leaves_staff_read"  on public.leaves for select using (public.is_staff());
create policy "leaves_self_insert" on public.leaves for insert with check (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "leaves_staff_write" on public.leaves for all    using (public.is_staff()) with check (public.is_staff());

-- ---- Warnings ----
drop policy if exists "warnings_self_read"  on public.warnings;
drop policy if exists "warnings_staff_read" on public.warnings;
drop policy if exists "warnings_staff_write" on public.warnings;
create policy "warnings_self_read"   on public.warnings for select using (employee_id in (select id from public.employees where user_id = auth.uid()));
create policy "warnings_staff_read"  on public.warnings for select using (public.is_staff());
create policy "warnings_staff_write" on public.warnings for all    using (public.is_staff()) with check (public.is_staff());

-- ---- Notifications ----
drop policy if exists "notif_self_or_broadcast" on public.notifications;
drop policy if exists "notif_self_update"        on public.notifications;
drop policy if exists "notif_authenticated_insert" on public.notifications;
drop policy if exists "notif_staff_write"        on public.notifications;
create policy "notif_self_or_broadcast" on public.notifications for select using (recipient_id is null or recipient_id = auth.uid());
create policy "notif_self_update"        on public.notifications for update using (recipient_id = auth.uid()) with check (recipient_id = auth.uid());
create policy "notif_authenticated_insert" on public.notifications for insert with check (auth.role() = 'authenticated');
create policy "notif_staff_write"        on public.notifications for all using (public.is_staff()) with check (public.is_staff());

-- ---- Audit logs ----
drop policy if exists "audit_admin_read"     on public.audit_logs;
drop policy if exists "audit_authenticated_insert" on public.audit_logs;
create policy "audit_admin_read"           on public.audit_logs for select using (public.is_staff());
create policy "audit_authenticated_insert" on public.audit_logs for insert with check (auth.role() = 'authenticated');

-- ====================  REALTIME  ====================
-- Enable realtime broadcast on the tables the app subscribes to.
alter publication supabase_realtime add table public.profiles;
alter publication supabase_realtime add table public.employees;
alter publication supabase_realtime add table public.attendance;
alter publication supabase_realtime add table public.attendance_sessions;
alter publication supabase_realtime add table public.tasks;
alter publication supabase_realtime add table public.announcements;
alter publication supabase_realtime add table public.salary_records;
alter publication supabase_realtime add table public.leaves;
alter publication supabase_realtime add table public.warnings;
alter publication supabase_realtime add table public.notifications;
alter publication supabase_realtime add table public.audit_logs;

-- ====================  STORAGE BUCKETS  ====================
-- Run these in the SQL editor too (or via Storage UI).
-- 'avatars' is public (so <img src=URL> works without signed URLs).
insert into storage.buckets (id, name, public)
  values ('avatars', 'avatars', true)
  on conflict (id) do nothing;
insert into storage.buckets (id, name, public)
  values ('exports', 'exports', false)
  on conflict (id) do nothing;
insert into storage.buckets (id, name, public)
  values ('payslips', 'payslips', false)
  on conflict (id) do nothing;

-- Allow each user to write under a folder named with their auth.uid().
drop policy if exists "avatars_owner_write" on storage.objects;
drop policy if exists "avatars_public_read" on storage.objects;
create policy "avatars_owner_write" on storage.objects
  for all using (
    bucket_id = 'avatars'
    and (auth.uid()::text = split_part(name, '/', 1))
  ) with check (
    bucket_id = 'avatars'
    and (auth.uid()::text = split_part(name, '/', 1))
  );
create policy "avatars_public_read" on storage.objects
  for select using (bucket_id = 'avatars');

-- Authenticated users can read their own exports/payslips
drop policy if exists "exports_owner_rw" on storage.objects;
create policy "exports_owner_rw" on storage.objects
  for all using (
    bucket_id in ('exports','payslips')
    and (auth.uid()::text = split_part(name, '/', 1))
  ) with check (
    bucket_id in ('exports','payslips')
    and (auth.uid()::text = split_part(name, '/', 1))
  );

-- ============================================================
--  DONE.  Now seed your fixed admin user — see README.md.
-- ============================================================
