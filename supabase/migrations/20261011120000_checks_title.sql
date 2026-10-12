alter table public.checks add column if not exists title text check (title is null or length(title) between 1 and 200);
comment on column public.checks.title is 'Название проверки (объект из ПЗ по умолчанию, можно переименовать).';
