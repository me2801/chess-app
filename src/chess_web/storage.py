"""Postgres persistence helpers for chess games."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Json

from .auth import AuthUser


class StorageError(RuntimeError):
    """Raised when database requests fail."""


@dataclass(frozen=True)
class DbConfig:
    dsn: str
    table: str = 'chess_app_games'


def get_db_config() -> Optional[DbConfig]:
    """Load database configuration from environment."""
    dsn = os.environ.get('SUPABASE_DB_URL') or os.environ.get('DATABASE_URL')
    if not dsn:
        return None
    return DbConfig(dsn=dsn)


def _connect(config: DbConfig) -> psycopg.Connection:
    return psycopg.connect(config.dsn, row_factory=dict_row)


def _ensure_finished_at(game_state: Dict[str, Any]) -> Optional[Any]:
    if not game_state.get('game_over'):
        return None
    finished_at = game_state.get('finished_at')
    if finished_at:
        return finished_at
    return datetime.now(timezone.utc)


def _result_for_player(game_state: Dict[str, Any], player_color: str = 'white') -> Optional[str]:
    if not game_state.get('game_over'):
        return None
    winner = game_state.get('winner')
    if not winner:
        return 'draw'
    return 'win' if winner == player_color else 'loss'


def _serialize_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    result = dict(row)
    finished_at = result.get('finished_at')
    if isinstance(finished_at, datetime):
        result['finished_at'] = finished_at.isoformat()
    created_at = result.get('created_at')
    if isinstance(created_at, datetime):
        result['created_at'] = created_at.isoformat()
    return result


def save_game_state(user: AuthUser, game_state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the current game state to Postgres."""
    config = get_db_config()
    if not config:
        raise StorageError('Database configuration missing')

    game_id = game_state.get('game_id')
    if not game_id:
        raise StorageError('Game id missing')

    finished_at = _ensure_finished_at(game_state)
    result = _result_for_player(game_state) if game_state.get('game_over') else None

    payload = {
        'game_id': game_id,
        'user_id': user.id,
        'user_email': user.email,
        'player_name': user.name,
        'result': result,
        'winner': game_state.get('winner'),
        'status_message': game_state.get('status_message'),
        'finished_at': finished_at,
        'moves_count': len(game_state.get('move_history') or []),
        'game_state': game_state,
        'game_over': bool(game_state.get('game_over')),
    }

    query = sql.SQL(
        """
        insert into {table} (
            game_id,
            user_id,
            user_email,
            player_name,
            result,
            winner,
            status_message,
            game_over,
            finished_at,
            moves_count,
            game_state
        )
        values (
            %(game_id)s,
            %(user_id)s,
            %(user_email)s,
            %(player_name)s,
            %(result)s,
            %(winner)s,
            %(status_message)s,
            %(game_over)s,
            %(finished_at)s,
            %(moves_count)s,
            %(game_state)s
        )
        on conflict (game_id) do update
        set
            user_email = excluded.user_email,
            player_name = excluded.player_name,
            result = excluded.result,
            winner = excluded.winner,
            status_message = excluded.status_message,
            game_over = excluded.game_over,
            finished_at = excluded.finished_at,
            moves_count = excluded.moves_count,
            game_state = excluded.game_state
        where {table}.user_id = excluded.user_id
        returning game_id
        """
    ).format(table=sql.Identifier(config.table))

    params = dict(payload)
    params['game_state'] = Json(payload['game_state'])

    try:
        with _connect(config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
    except Exception as exc:  # pragma: no cover - database connectivity
        raise StorageError(str(exc)) from exc

    if not row:
        raise StorageError('Game update denied')

    return {'game_id': row.get('game_id')}


def list_user_games(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent games for a user."""
    config = get_db_config()
    if not config:
        raise StorageError('Database configuration missing')

    query = sql.SQL(
        """
        select
            game_id,
            finished_at,
            result,
            winner,
            status_message,
            moves_count,
            player_name,
            game_over
        from {table}
        where user_id = %s
        order by finished_at desc nulls last, created_at desc
        limit %s
        """
    ).format(table=sql.Identifier(config.table))

    try:
        with _connect(config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, limit))
                rows = cur.fetchall()
    except Exception as exc:  # pragma: no cover - database connectivity
        raise StorageError(str(exc)) from exc

    return [_serialize_row(row) for row in rows]


def get_game(game_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return a single game, optionally scoped to a user."""
    config = get_db_config()
    if not config:
        raise StorageError('Database configuration missing')

    if user_id:
        query = sql.SQL(
            "select * from {table} where game_id = %s and user_id = %s limit 1"
        ).format(table=sql.Identifier(config.table))
        params = (game_id, user_id)
    else:
        query = sql.SQL(
            "select * from {table} where game_id = %s limit 1"
        ).format(table=sql.Identifier(config.table))
        params = (game_id,)

    try:
        with _connect(config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
    except Exception as exc:  # pragma: no cover - database connectivity
        raise StorageError(str(exc)) from exc

    return _serialize_row(row)


def list_games_for_leaderboard(limit: int = 500) -> List[Dict[str, Any]]:
    """Return finished games for leaderboard calculation."""
    config = get_db_config()
    if not config:
        raise StorageError('Database configuration missing')

    query = sql.SQL(
        """
        select user_id, player_name, result, finished_at
        from {table}
        where game_over = true
        order by finished_at desc nulls last
        limit %s
        """
    ).format(table=sql.Identifier(config.table))

    try:
        with _connect(config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                rows = cur.fetchall()
    except Exception as exc:  # pragma: no cover - database connectivity
        raise StorageError(str(exc)) from exc

    return [_serialize_row(row) for row in rows]


def get_user_stats(user_id: str, streak_window: int = 200) -> Dict[str, Any]:
    """Return aggregated stats and streak for a user."""
    config = get_db_config()
    if not config:
        raise StorageError('Database configuration missing')

    summary_query = sql.SQL(
        """
        select
            coalesce(sum(case when result = 'win' then 1 else 0 end), 0) as wins,
            coalesce(sum(case when result = 'loss' then 1 else 0 end), 0) as losses,
            coalesce(sum(case when result = 'draw' then 1 else 0 end), 0) as draws
        from {table}
        where user_id = %s
          and game_over = true
        """
    ).format(table=sql.Identifier(config.table))

    streak_query = sql.SQL(
        """
        select result
        from {table}
        where user_id = %s
          and game_over = true
        order by finished_at desc nulls last, created_at desc
        limit %s
        """
    ).format(table=sql.Identifier(config.table))

    try:
        with _connect(config) as conn:
            with conn.cursor() as cur:
                cur.execute(summary_query, (user_id,))
                summary = cur.fetchone() or {}

                cur.execute(streak_query, (user_id, streak_window))
                rows = cur.fetchall()
    except Exception as exc:  # pragma: no cover - database connectivity
        raise StorageError(str(exc)) from exc

    results = [row.get('result') for row in rows if row]
    streak = 0
    if results:
        first = results[0]
        if first == 'win':
            for result in results:
                if result == 'win':
                    streak += 1
                else:
                    break
        elif first == 'loss':
            for result in results:
                if result == 'loss':
                    streak -= 1
                else:
                    break

    return {
        'wins': int(summary.get('wins') or 0),
        'losses': int(summary.get('losses') or 0),
        'draws': int(summary.get('draws') or 0),
        'streak': streak,
    }


def build_leaderboard(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate leaderboard stats from game entries."""
    stats: Dict[str, Dict[str, Any]] = {}
    for row in entries:
        user_id = row.get('user_id') or 'unknown'
        player_name = row.get('player_name') or 'Anonymous'
        result = row.get('result') or 'draw'
        entry = stats.setdefault(user_id, {
            'user_id': user_id,
            'player_name': player_name,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'points': 0
        })
        if result == 'win':
            entry['wins'] += 1
            entry['points'] += 2
        elif result == 'loss':
            entry['losses'] += 1
        else:
            entry['draws'] += 1
            entry['points'] += 1

    leaderboard = list(stats.values())
    leaderboard.sort(
        key=lambda item: (
            -item['points'],
            -item['wins'],
            -item['draws'],
            item['player_name'].lower()
        )
    )
    for idx, entry in enumerate(leaderboard, start=1):
        entry['rank'] = idx
    return leaderboard
