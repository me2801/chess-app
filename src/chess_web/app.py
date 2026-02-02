"""Flask application for chess game."""

from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from .models import Game
from dotenv import load_dotenv
import os
import shutil
import time
import uuid


def _parse_position(value):
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


def create_app():
    """Create and configure the Flask application."""
    load_dotenv()
    app = Flask(__name__)

    # Configure session
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['DEBUG_UI'] = os.environ.get('DEBUG', '').lower() in {'1', 'true', 'yes', 'on'}
    app.config['SESSION_FILE_DIR'] = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'flask_session')
    )
    app.config['ASSET_VERSION'] = str(int(time.time()))
    app.config['SERVER_START_ID'] = uuid.uuid4().hex
    if os.path.isdir(app.config['SESSION_FILE_DIR']):
        for entry in os.listdir(app.config['SESSION_FILE_DIR']):
            path = os.path.join(app.config['SESSION_FILE_DIR'], entry)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception:
                pass
    Session(app)

    # Register the API blueprint with Swagger documentation
    from .api import api_bp
    app.register_blueprint(api_bp)

    @app.after_request
    def disable_cache(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    @app.route('/')
    def index():
        """Main game page."""
        # Always start a fresh game on page load to avoid stale history.
        session.clear()
        session['server_start_id'] = app.config['SERVER_START_ID']
        game = Game()
        session['game'] = game.to_dict()

        return render_template('game.html', game=game, debug_ui=app.config['DEBUG_UI'])

    @app.route('/new-game', methods=['POST'])
    def new_game():
        """Start a new game."""
        session.clear()
        session['server_start_id'] = app.config['SERVER_START_ID']
        game = Game()
        session['game'] = game.to_dict()

        return jsonify({
            'success': True,
            'message': 'New game started',
            'game_state': game.to_dict()
        })

    @app.route('/move', methods=['POST'])
    def make_move():
        """Process a move request."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid move payload'
            }), 400

        if 'game' not in session:
            return jsonify({
                'success': False,
                'message': 'No active game'
            }), 400
        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            return jsonify({
                'success': False,
                'message': 'Session expired'
            }), 400

        # Parse move data
        from_pos = _parse_position(data.get('from'))
        to_pos = _parse_position(data.get('to'))
        promotion_piece = data.get('promotion_piece', 'queen')

        if not from_pos or not to_pos:
            return jsonify({
                'success': False,
                'message': 'Invalid move format'
            }), 400

        # Load game and make move
        game = Game.from_dict(session['game'])
        result = game.make_move(from_pos, to_pos, promotion_piece)

        # Save updated game state
        session['game'] = game.to_dict()
        session.modified = True

        # Include full game state in response
        result['game_state'] = game.to_dict()

        return jsonify(result)

    @app.route('/ai-move', methods=['POST'])
    def ai_move():
        """Make an AI move if it's AI's turn."""
        if 'game' not in session:
            return jsonify({
                'success': False,
                'message': 'No active game'
            }), 400
        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            return jsonify({
                'success': False,
                'message': 'Session expired'
            }), 400

        game = Game.from_dict(session['game'])
        result = game.make_ai_move() or {
            'success': False,
            'message': 'No AI move available'
        }

        session['game'] = game.to_dict()
        session.modified = True
        result['game_state'] = game.to_dict()

        return jsonify(result)

    @app.route('/legal-moves', methods=['POST'])
    def get_legal_moves():
        """Get legal moves for a piece."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request payload'
            }), 400

        if 'game' not in session:
            return jsonify({
                'success': False,
                'message': 'No active game'
            }), 400
        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            return jsonify({
                'success': False,
                'message': 'Session expired'
            }), 400

        position = _parse_position(data.get('position'))
        if not position:
            return jsonify({
                'success': False,
                'message': 'Invalid position'
            }), 400

        game = Game.from_dict(session['game'])
        legal_moves = game.get_legal_moves(position)

        return jsonify({
            'success': True,
            'legal_moves': legal_moves
        })

    @app.route('/game-state', methods=['GET'])
    def get_game_state():
        """Get current game state."""
        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            session.clear()
            session['server_start_id'] = app.config['SERVER_START_ID']
            game = Game()
            session['game'] = game.to_dict()
        elif 'game' not in session:
            game = Game()
            session['game'] = game.to_dict()
        else:
            game = Game.from_dict(session['game'])

        return jsonify(game.to_dict())

    @app.route('/load-game', methods=['POST'])
    def load_game():
        """Load a saved game state."""
        data = request.get_json(silent=True)
        if not data or 'game_state' not in data:
            return jsonify({
                'success': False,
                'message': 'Invalid load game payload'
            }), 400

        try:
            game = Game.from_dict(data['game_state'])
            session['game'] = game.to_dict()
            session['server_start_id'] = app.config['SERVER_START_ID']
            session.modified = True

            return jsonify({
                'success': True,
                'message': 'Game loaded successfully',
                'game_state': game.to_dict()
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Failed to load game: {str(e)}'
            }), 400

    @app.route('/undo', methods=['POST'])
    def undo_move():
        """Undo the last move."""
        if 'game' not in session:
            return jsonify({
                'success': False,
                'message': 'No active game'
            }), 400
        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            return jsonify({
                'success': False,
                'message': 'Session expired'
            }), 400

        game = Game.from_dict(session['game'])
        result = game.undo_move()

        session['game'] = game.to_dict()
        session.modified = True

        if result['success']:
            result['game_state'] = game.to_dict()

        return jsonify(result)

    @app.route('/resign', methods=['POST'])
    def resign():
        """Handle player resignation."""
        data = request.get_json()
        color = data.get('color', 'white')

        if 'game' not in session:
            return jsonify({
                'success': False,
                'message': 'No active game'
            }), 400
        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            return jsonify({
                'success': False,
                'message': 'Session expired'
            }), 400

        game = Game.from_dict(session['game'])
        result = game.resign(color)

        session['game'] = game.to_dict()
        session.modified = True

        return jsonify(result)

    return app


def main():
    """Main entry point for running the application."""
    import sys

    # Handle Windows console encoding
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("\n" + "="*60)
    print("Chess Web Application Starting...")
    print("="*60)
    print("\nOpen your browser to: http://127.0.0.1:5000")
    print("API Documentation:    http://127.0.0.1:5000/api/docs")
    print("\nPress CTRL+C to stop the server\n")

    app = create_app()
    app.run(debug=True, host='127.0.0.1', port=5000)


# For development
if __name__ == '__main__':
    main()
