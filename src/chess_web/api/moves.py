"""Move-related API endpoints."""

from flask import session, request, current_app
from flask_restx import Namespace, Resource, fields

from ..models import Game

ns = Namespace('moves', description='Move operations')

# API Models
move_request = ns.model('MoveRequest', {
    'from': fields.List(fields.Integer, required=True,
                        description='Starting position [row, col]'),
    'to': fields.List(fields.Integer, required=True,
                      description='Target position [row, col]'),
    'promotion_piece': fields.String(default='queen',
                                     description='Piece type for pawn promotion')
})

move_response = ns.model('MoveResponse', {
    'success': fields.Boolean(description='Whether the move was successful'),
    'message': fields.String(description='Result message'),
    'in_check': fields.Boolean(description='Whether opponent is now in check'),
    'game_over': fields.Boolean(description='Whether the game has ended'),
    'winner': fields.String(description='Winner if game is over'),
    'captured': fields.Boolean(description='Whether a piece was captured'),
    'game_state': fields.Raw(description='Updated game state')
})

undo_response = ns.model('UndoResponse', {
    'success': fields.Boolean(description='Whether undo was successful'),
    'message': fields.String(description='Result message'),
    'in_check': fields.Boolean(description='Whether current player is in check'),
    'game_state': fields.Raw(description='Updated game state')
})

ai_move_response = ns.model('AIMoveResponse', {
    'success': fields.Boolean(description='Whether AI move was successful'),
    'message': fields.String(description='Result message'),
    'ai_move': fields.Raw(description='The move made by AI'),
    'in_check': fields.Boolean(description='Whether player is now in check'),
    'game_over': fields.Boolean(description='Whether the game has ended'),
    'game_state': fields.Raw(description='Updated game state')
})


def _parse_position(value):
    """Parse a position value into a (row, col) tuple."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(',')]
        if len(parts) == 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except (TypeError, ValueError):
                return None
    return None


def _validate_session():
    """Validate the session is active."""
    if 'game' not in session:
        return False, 'No active game'
    if session.get('server_start_id') != current_app.config['SERVER_START_ID']:
        return False, 'Session expired'
    return True, None


@ns.route('/')
class MakeMove(Resource):
    @ns.doc('make_move')
    @ns.expect(move_request)
    @ns.marshal_with(move_response)
    @ns.response(200, 'Move processed')
    @ns.response(400, 'Invalid move')
    def post(self):
        """Make a chess move."""
        data = request.get_json(silent=True)
        if not data:
            ns.abort(400, 'Invalid move payload')

        valid, error = _validate_session()
        if not valid:
            ns.abort(400, error)

        from_pos = _parse_position(data.get('from'))
        to_pos = _parse_position(data.get('to'))
        promotion_piece = data.get('promotion_piece', 'queen')

        if not from_pos or not to_pos:
            ns.abort(400, 'Invalid move format')

        game = Game.from_dict(session['game'])
        result = game.make_move(from_pos, to_pos, promotion_piece)

        session['game'] = game.to_dict()
        session.modified = True

        result['game_state'] = game.to_dict()
        return result


@ns.route('/undo')
class UndoMove(Resource):
    @ns.doc('undo_move')
    @ns.marshal_with(undo_response)
    @ns.response(200, 'Move undone')
    @ns.response(400, 'Cannot undo')
    def post(self):
        """Undo the last move."""
        valid, error = _validate_session()
        if not valid:
            ns.abort(400, error)

        game = Game.from_dict(session['game'])
        result = game.undo_move()

        session['game'] = game.to_dict()
        session.modified = True

        if result['success']:
            result['game_state'] = game.to_dict()

        return result


@ns.route('/ai')
class AIMove(Resource):
    @ns.doc('ai_move')
    @ns.marshal_with(ai_move_response)
    @ns.response(200, 'AI move made')
    @ns.response(400, 'No AI move available')
    def post(self):
        """Request an AI move."""
        valid, error = _validate_session()
        if not valid:
            ns.abort(400, error)

        game = Game.from_dict(session['game'])
        result = game.make_ai_move() or {
            'success': False,
            'message': 'No AI move available'
        }

        session['game'] = game.to_dict()
        session.modified = True
        result['game_state'] = game.to_dict()

        return result
