"""Game persistence API endpoints (save/load)."""

from flask import session, request, current_app
from flask_restx import Namespace, Resource, fields

from ..models import Game

ns = Namespace('persistence', description='Save and load game operations')

# API Models
load_game_request = ns.model('LoadGameRequest', {
    'game_state': fields.Raw(required=True, description='Game state object to load')
})

load_game_response = ns.model('LoadGameResponse', {
    'success': fields.Boolean(description='Whether load was successful'),
    'message': fields.String(description='Result message'),
    'game_state': fields.Raw(description='Loaded game state')
})

export_response = ns.model('ExportResponse', {
    'success': fields.Boolean(description='Whether export was successful'),
    'pgn': fields.String(description='Game in PGN format'),
    'fen': fields.String(description='Current position in FEN format')
})


@ns.route('/load')
class LoadGame(Resource):
    @ns.doc('load_game')
    @ns.expect(load_game_request)
    @ns.marshal_with(load_game_response)
    @ns.response(200, 'Game loaded')
    @ns.response(400, 'Invalid game state')
    def post(self):
        """Load a previously saved game state."""
        data = request.get_json(silent=True)
        if not data or 'game_state' not in data:
            ns.abort(400, 'Invalid load game payload')

        try:
            game = Game.from_dict(data['game_state'])
            session['game'] = game.to_dict()
            session['server_start_id'] = current_app.config['SERVER_START_ID']
            session.modified = True

            return {
                'success': True,
                'message': 'Game loaded successfully',
                'game_state': game.to_dict()
            }
        except Exception as e:
            ns.abort(400, f'Failed to load game: {str(e)}')


@ns.route('/export')
class ExportGame(Resource):
    @ns.doc('export_game')
    @ns.marshal_with(export_response)
    @ns.response(200, 'Game exported')
    @ns.response(400, 'No active game')
    def get(self):
        """Export the current game in PGN and FEN formats."""
        if 'game' not in session:
            ns.abort(400, 'No active game')

        game = Game.from_dict(session['game'])

        # Generate PGN
        pgn_lines = [
            '[Event "Chess Web Game"]',
            '[Site "Local"]',
            f'[Result "{_get_result(game)}"]',
            ''
        ]

        # Add moves in PGN format
        move_text = []
        for i, move in enumerate(game.move_history):
            if i % 2 == 0:
                move_text.append(f"{i // 2 + 1}.")
            move_text.append(move['notation'])

        if game.game_over:
            move_text.append(_get_result(game))

        pgn_lines.append(' '.join(move_text))

        # Generate FEN (simplified)
        fen = _generate_fen(game)

        return {
            'success': True,
            'pgn': '\n'.join(pgn_lines),
            'fen': fen
        }


def _get_result(game):
    """Get PGN result string."""
    if not game.game_over:
        return '*'
    if game.winner == 'white':
        return '1-0'
    if game.winner == 'black':
        return '0-1'
    return '1/2-1/2'


def _generate_fen(game):
    """Generate FEN string for current position."""
    fen_parts = []

    # Board position
    rows = []
    for row in range(8):
        fen_row = ''
        empty_count = 0
        for col in range(8):
            piece = game.board.get_piece(row, col)
            if piece is None:
                empty_count += 1
            else:
                if empty_count > 0:
                    fen_row += str(empty_count)
                    empty_count = 0
                piece_char = _get_piece_char(piece)
                fen_row += piece_char
        if empty_count > 0:
            fen_row += str(empty_count)
        rows.append(fen_row)

    fen_parts.append('/'.join(rows))

    # Active color
    fen_parts.append('w' if game.current_turn == 'white' else 'b')

    # Castling rights (simplified - would need proper tracking)
    fen_parts.append('KQkq')

    # En passant target
    if game.en_passant_target:
        row, col = game.en_passant_target
        ep_square = chr(ord('a') + col) + str(8 - row)
        fen_parts.append(ep_square)
    else:
        fen_parts.append('-')

    # Halfmove clock
    fen_parts.append(str(game.halfmove_clock))

    # Fullmove number
    fen_parts.append(str(len(game.move_history) // 2 + 1))

    return ' '.join(fen_parts)


def _get_piece_char(piece):
    """Get FEN character for a piece."""
    type_map = {
        'King': 'K',
        'Queen': 'Q',
        'Rook': 'R',
        'Bishop': 'B',
        'Knight': 'N',
        'Pawn': 'P'
    }
    char = type_map.get(piece.__class__.__name__, '?')
    return char if piece.color == 'white' else char.lower()
