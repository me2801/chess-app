"""Game state API endpoints."""

from flask import session, current_app, request
from flask_restx import Namespace, Resource, fields

from ..models import Game
from ..auth import get_current_user

ns = Namespace('game', description='Game state operations')

# API Models for documentation
position_model = ns.model('Position', {
    'row': fields.Integer(required=True, description='Row index (0-7)', min=0, max=7),
    'col': fields.Integer(required=True, description='Column index (0-7)', min=0, max=7)
})

piece_model = ns.model('Piece', {
    'type': fields.String(description='Piece type (pawn, rook, knight, bishop, queen, king)'),
    'color': fields.String(description='Piece color (white, black)'),
    'position': fields.List(fields.Integer, description='Position [row, col]'),
    'has_moved': fields.Boolean(description='Whether the piece has moved')
})

board_model = ns.model('Board', {
    'board': fields.List(fields.List(fields.Nested(piece_model, allow_null=True)),
                         description='8x8 board grid')
})

game_state_model = ns.model('GameState', {
    'game_id': fields.String(description='Unique game identifier'),
    'board': fields.Nested(board_model, description='Current board state'),
    'current_turn': fields.String(description='Current player turn (white/black)'),
    'move_history': fields.List(fields.Raw, description='List of moves made'),
    'captured_pieces': fields.Raw(description='Captured pieces by color'),
    'game_over': fields.Boolean(description='Whether the game has ended'),
    'winner': fields.String(description='Winner color if game is over'),
    'status_message': fields.String(description='Current game status message'),
    'in_check': fields.Boolean(description='Whether current player is in check'),
    'finished_at': fields.String(description='Timestamp when the game finished')
})

new_game_response = ns.model('NewGameResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Response message'),
    'game_state': fields.Nested(game_state_model, description='New game state')
})

legal_moves_request = ns.model('LegalMovesRequest', {
    'position': fields.List(fields.Integer, required=True,
                           description='Position [row, col] of the piece')
})

legal_moves_response = ns.model('LegalMovesResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'legal_moves': fields.List(fields.List(fields.Integer),
                               description='List of legal move positions [[row, col], ...]')
})


def _get_game():
    """Get current game from session or create new one."""
    if session.get('server_start_id') != current_app.config['SERVER_START_ID']:
        auth = session.get('auth')
        session.clear()
        if auth:
            session['auth'] = auth
        session['server_start_id'] = current_app.config['SERVER_START_ID']
        game = Game()
        session['game'] = game.to_dict()
    elif 'game' not in session:
        game = Game()
        session['game'] = game.to_dict()
    else:
        game = Game.from_dict(session['game'])
    return game


def _validate_session():
    """Validate the session is active."""
    user, error = get_current_user(request)
    if not user:
        return False, error or 'Unauthorized'
    if 'game' not in session:
        return False, 'No active game'
    if session.get('server_start_id') != current_app.config['SERVER_START_ID']:
        return False, 'Session expired'
    return True, None


def _require_auth():
    user, error = get_current_user(request)
    if not user:
        ns.abort(401, error or 'Unauthorized')
    return user


@ns.route('/state')
class GameState(Resource):
    @ns.doc('get_game_state')
    @ns.marshal_with(game_state_model)
    @ns.response(200, 'Success')
    def get(self):
        """Get current game state."""
        _require_auth()
        game = _get_game()
        return game.to_dict()


@ns.route('/new')
class NewGame(Resource):
    @ns.doc('start_new_game')
    @ns.marshal_with(new_game_response)
    @ns.response(200, 'New game started')
    def post(self):
        """Start a new game."""
        _require_auth()
        auth = session.get('auth')
        session.clear()
        if auth:
            session['auth'] = auth
        session['server_start_id'] = current_app.config['SERVER_START_ID']
        game = Game()
        session['game'] = game.to_dict()

        return {
            'success': True,
            'message': 'New game started',
            'game_state': game.to_dict()
        }


@ns.route('/legal-moves')
class LegalMoves(Resource):
    @ns.doc('get_legal_moves')
    @ns.expect(legal_moves_request)
    @ns.marshal_with(legal_moves_response)
    @ns.response(200, 'Success')
    @ns.response(400, 'Invalid request')
    def post(self):
        """Get legal moves for a piece at the given position."""
        from flask import request

        data = request.get_json(silent=True)
        if not data:
            ns.abort(400, 'Invalid request payload')

        valid, error = _validate_session()
        if not valid:
            ns.abort(400, error)

        position = data.get('position')
        if not position or len(position) != 2:
            ns.abort(400, 'Invalid position')

        try:
            position = (int(position[0]), int(position[1]))
        except (TypeError, ValueError):
            ns.abort(400, 'Invalid position format')

        game = Game.from_dict(session['game'])
        legal_moves = game.get_legal_moves(position)

        return {
            'success': True,
            'legal_moves': legal_moves
        }


@ns.route('/resign')
class Resign(Resource):
    @ns.doc('resign_game')
    @ns.response(200, 'Resignation processed')
    @ns.response(400, 'Invalid request')
    def post(self):
        """Resign the current game."""
        from flask import request

        data = request.get_json()
        color = data.get('color', 'white')

        valid, error = _validate_session()
        if not valid:
            ns.abort(400, error)

        game = Game.from_dict(session['game'])
        result = game.resign(color)

        session['game'] = game.to_dict()
        session.modified = True

        return result
