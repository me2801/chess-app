"""Game history and leaderboard endpoints."""

from flask import request
from flask_restx import Namespace, Resource, fields

from ..auth import get_current_user
from ..replay import build_replay_states
from ..storage import (
    StorageError,
    build_leaderboard,
    get_game,
    get_user_stats,
    list_games_for_leaderboard,
    list_user_games,
)

ns = Namespace('records', description='Game history and leaderboard')

game_summary_model = ns.model('GameSummary', {
    'game_id': fields.String(description='Game id'),
    'finished_at': fields.String(description='Finished timestamp'),
    'result': fields.String(description='Result (win/draw/loss)'),
    'winner': fields.String(description='Winner color'),
    'status_message': fields.String(description='Final status message'),
    'moves_count': fields.Integer(description='Number of moves'),
    'player_name': fields.String(description='Player display name'),
    'game_over': fields.Boolean(description='Whether the game is finished'),
})

history_response = ns.model('HistoryResponse', {
    'games': fields.List(fields.Nested(game_summary_model))
})

leaderboard_entry = ns.model('LeaderboardEntry', {
    'rank': fields.Integer(description='Rank'),
    'user_id': fields.String(description='User id'),
    'player_name': fields.String(description='Display name'),
    'wins': fields.Integer(description='Win count'),
    'draws': fields.Integer(description='Draw count'),
    'losses': fields.Integer(description='Loss count'),
    'points': fields.Integer(description='Total points'),
})

leaderboard_response = ns.model('LeaderboardResponse', {
    'leaders': fields.List(fields.Nested(leaderboard_entry))
})

stats_response = ns.model('StatsResponse', {
    'wins': fields.Integer(description='Win count'),
    'losses': fields.Integer(description='Loss count'),
    'draws': fields.Integer(description='Draw count'),
    'streak': fields.Integer(description='Current streak (positive=win, negative=loss)'),
})

review_response = ns.model('ReviewResponse', {
    'game': fields.Nested(game_summary_model),
    'replay': fields.List(fields.Raw, description='Replay game states'),
    'moves': fields.List(fields.Raw, description='Move history')
})


@ns.route('/history')
class History(Resource):
    @ns.doc('list_history')
    @ns.marshal_with(history_response)
    @ns.response(200, 'History loaded')
    @ns.response(401, 'Unauthorized')
    def get(self):
        """List finished games for the current user."""
        user, error = get_current_user(request)
        if not user:
            ns.abort(401, error or 'Unauthorized')

        limit_raw = request.args.get('limit', '50')
        try:
            limit = min(100, max(1, int(limit_raw)))
        except ValueError:
            limit = 50

        try:
            games = list_user_games(user.id, limit=limit)
        except StorageError as exc:
            ns.abort(500, str(exc))
        return {'games': games}


@ns.route('/history/<string:game_id>')
class Review(Resource):
    @ns.doc('review_game')
    @ns.marshal_with(review_response)
    @ns.response(200, 'Review loaded')
    @ns.response(401, 'Unauthorized')
    @ns.response(404, 'Not found')
    def get(self, game_id: str):
        """Load a completed game and replay states."""
        user, error = get_current_user(request)
        if not user:
            ns.abort(401, error or 'Unauthorized')

        try:
            record = get_game(game_id, user.id)
        except StorageError as exc:
            ns.abort(500, str(exc))

        if not record:
            ns.abort(404, 'Game not found')

        game_state = record.get('game_state') or {}
        move_history = game_state.get('move_history') or []
        replay = build_replay_states(move_history)

        summary = {
            'game_id': record.get('game_id'),
            'finished_at': record.get('finished_at'),
            'result': record.get('result'),
            'winner': record.get('winner'),
            'status_message': record.get('status_message'),
            'moves_count': record.get('moves_count'),
            'player_name': record.get('player_name'),
            'game_over': record.get('game_over')
        }

        return {
            'game': summary,
            'replay': replay,
            'moves': move_history
        }


@ns.route('/stats')
class Stats(Resource):
    @ns.doc('stats')
    @ns.marshal_with(stats_response)
    @ns.response(200, 'Stats loaded')
    @ns.response(401, 'Unauthorized')
    def get(self):
        """Return stats for the current user."""
        user, error = get_current_user(request)
        if not user:
            ns.abort(401, error or 'Unauthorized')

        try:
            stats = get_user_stats(user.id)
        except StorageError as exc:
            ns.abort(500, str(exc))
        return stats


@ns.route('/leaderboard')
class Leaderboard(Resource):
    @ns.doc('leaderboard')
    @ns.marshal_with(leaderboard_response)
    @ns.response(200, 'Leaderboard loaded')
    def get(self):
        """Return leaderboard based on finished games."""
        limit_raw = request.args.get('limit', '20')
        try:
            limit = min(100, max(1, int(limit_raw)))
        except ValueError:
            limit = 20

        try:
            entries = list_games_for_leaderboard(limit=1000)
        except StorageError as exc:
            ns.abort(500, str(exc))

        leaders = build_leaderboard(entries)[:limit]
        return {'leaders': leaders}
