create table if not exists public.access_requests (
  id bigint generated always as identity primary key,
  email text not null check (length(email) between 3 and 320),
  organization text not null check (length(organization) between 1 and 200),
  comment text not null default '' check (length(comment) <= 1000),
  created_at timestamptz not null default now()
);
create index if not exists access_requests_email_created_idx on public.access_requests (email, created_at desc);
alter table public.access_requests enable row level security;
comment on table public.access_requests is 'Заявки «Запросить доступ» с лендинга. Доступ только с сервера.';
