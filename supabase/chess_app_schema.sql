-- Chess app Supabase schema

create table if not exists chess_app_games (
    game_id text primary key,
    user_id uuid not null,
    user_email text,
    player_name text,
    result text check (result in ('win', 'draw', 'loss')),
    winner text,
    status_message text,
    game_over boolean not null default false,
    finished_at timestamptz,
    moves_count integer not null default 0,
    game_state jsonb not null,
    created_at timestamptz not null default now()
);

create index if not exists chess_app_games_user_id_idx
    on chess_app_games(user_id);

create index if not exists chess_app_games_finished_at_idx
    on chess_app_games(finished_at desc);

alter table chess_app_games enable row level security;

-- Tight RLS (recommended when using service role key from server)
drop policy if exists "Users can read their games" on chess_app_games;
create policy "Users can read their games"
    on chess_app_games
    for select
    using (auth.uid() = user_id);

drop policy if exists "Users can insert their games" on chess_app_games;
create policy "Users can insert their games"
    on chess_app_games
    for insert
    with check (auth.uid() = user_id);

-- Optional migration helpers for existing tables
alter table chess_app_games add column if not exists game_over boolean default false;
alter table chess_app_games alter column finished_at drop not null;
alter table chess_app_games alter column result drop not null;
alter table chess_app_games drop constraint if exists chess_app_games_result_check;
alter table chess_app_games add constraint chess_app_games_result_check
    check (result in ('win', 'draw', 'loss'));
