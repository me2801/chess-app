"""Flask application for chess game."""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, abort
from flask_session import Session
from asgiref.wsgi import WsgiToAsgi
from .models import Game
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from urllib.parse import quote
import asyncio
import os
import shutil
import threading
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
    app.config['SECRET_KEY'] = os.environ.get('METASUITE_SESSION_SECRET', 'dev-secret-change-in-production')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_COOKIE_NAME'] = os.environ.get('METASUITE_SESSION_COOKIE_NAME', 'metasuite_session')
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('METASUITE_SECURE_COOKIES', 'false').lower() in {
        '1', 'true', 'yes', 'on'
    }
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('METASUITE_SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    # Support nested deployment under a subdirectory (ROOT_PATH for ASGI, APPLICATION_ROOT for WSGI)
    app.config['APPLICATION_ROOT'] = os.environ.get('ROOT_PATH', os.environ.get('APPLICATION_ROOT', '/'))
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

    from supabase_auth import AuthConfig, get_client, supabase_anon_key, supabase_url
    import supabase_auth as supabase_auth_pkg

    auth_config = AuthConfig(
        app_name=os.environ.get('APP_NAME', 'Chess Web'),
        app_short_name=os.environ.get('APP_SHORT_NAME', 'Chess'),
        login_title=os.environ.get('AUTH_LOGIN_TITLE', 'Sign in'),
        login_subtitle=os.environ.get('AUTH_LOGIN_SUBTITLE', 'Access your games'),
        logout_title=os.environ.get('AUTH_LOGOUT_TITLE', 'Signed out'),
        logout_subtitle=os.environ.get('AUTH_LOGOUT_SUBTITLE', 'You have been successfully signed out.'),
        home_path='/',
        login_path='/login',
        logout_path='/logout',
        login_api_path='/api/auth/login',
        session_api_path='/api/auth/session',
        css_path='/static/auth.css',
    )

    auth_template_dir = os.path.join(
        os.path.dirname(supabase_auth_pkg.__file__), 'front', 'templates'
    )
    auth_templates = Environment(
        loader=FileSystemLoader(auth_template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    def _prefixed_path(path: str) -> str:
        root = (app.config.get('APPLICATION_ROOT') or '').rstrip('/')
        if not root or root == '/':
            return path
        if path == root or path.startswith(root + '/'):
            return path
        if path.startswith('/'):
            return f"{root}{path}"
        return f"{root}/{path}"

    def _ensure_prefixed_path(path: str) -> str:
        return _prefixed_path(path)

    def _safe_next_path(raw: str) -> str:
        if not raw or not raw.startswith('/'):
            return auth_config.home_path
        return raw

    def _render_auth_template(template_name: str, **context):
        template = auth_templates.get_template(template_name)
        html = template.render(
            **context,
            url_for=url_for,
        )
        return html

    # Register the API blueprint with Swagger documentation
    from .api import api_bp
    app.register_blueprint(api_bp)

    def _require_auth():
        from .auth import get_current_user

        user, error = get_current_user(request)
        if not user:
            return None, (jsonify({'success': False, 'message': error or 'Unauthorized'}), 401)
        return user, None

    def _reset_game_session():
        auth = session.get('auth')
        session.clear()
        if auth:
            session['auth'] = auth

    def _store_game_state(game):
        from .auth import get_current_user
        from .storage import save_game_state, StorageError

        user, _error = get_current_user(request)
        if not user:
            return
        game_state = game.to_dict()

        def _persist(user_snapshot, state_snapshot):
            try:
                save_game_state(user_snapshot, state_snapshot)
            except StorageError as exc:
                app.logger.warning("Database save failed: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                app.logger.warning("Unexpected save error: %s", exc)

        threading.Thread(
            target=_persist,
            args=(user, game_state),
            daemon=True
        ).start()

    def _login_redirect(next_path: str):
        safe_next = _safe_next_path(next_path)
        safe_next = _ensure_prefixed_path(safe_next)
        login_url = _prefixed_path(auth_config.login_path)
        return redirect(f"{login_url}?next={quote(safe_next)}")

    @app.route('/static/auth.css', endpoint='auth_css')
    def auth_css():
        """Serve overridden auth CSS."""
        return send_from_directory(os.path.join(app.static_folder, 'css'), 'auth.css')

    @app.route('/login')
    def login():
        """Render the Supabase auth login form."""
        next_path = request.args.get('next', '') or auth_config.home_path
        next_path = _ensure_prefixed_path(_safe_next_path(next_path))
        return _render_auth_template(
            'login.html',
            request=request,
            next=next_path,
            supabase_configured=bool(supabase_url() and supabase_anon_key()),
            config=auth_config,
            prefixed=lambda path: _prefixed_path(path),
        )

    @app.route('/logout')
    def logout():
        """Clear session and render logout page."""
        session.clear()
        return _render_auth_template(
            'logout.html',
            request=request,
            config=auth_config,
            prefixed=lambda path: _prefixed_path(path),
        )

    @app.route('/api/auth/login', methods=['POST'])
    @app.route('/api/auth/session', methods=['POST'])
    def auth_login():
        """Handle login via Supabase password grant."""
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        password = (data.get('password') or '').strip()
        next_path = (data.get('next') or '').strip() or auth_config.home_path
        next_path = _ensure_prefixed_path(_safe_next_path(next_path))

        if not email or not password:
            return jsonify({'ok': False, 'error': 'Email and password are required.'}), 400

        client = get_client()
        if not client.is_configured:
            return jsonify({'ok': False, 'error': 'Supabase is not configured.'}), 503

        try:
            payload = asyncio.run(client.sign_in_with_password(email, password))
        except Exception as exc:  # pragma: no cover - external dependency
            return jsonify({'ok': False, 'error': f'Authentication failed: {exc}'}), 401

        if not payload:
            return jsonify({'ok': False, 'error': 'Invalid credentials.'}), 401

        user = payload.get('user') or {}
        user_id = user.get('id')
        if not user_id:
            return jsonify({'ok': False, 'error': 'Invalid credentials.'}), 401

        app_metadata = user.get('app_metadata') or {}
        user_metadata = user.get('user_metadata') or {}
        roles = app_metadata.get('roles') or []
        if isinstance(roles, str):
            roles = [roles]

        session['auth'] = {
            'user_id': user_id,
            'email': user.get('email') or email,
            'name': user_metadata.get('full_name') or user_metadata.get('name') or email,
            'roles': roles,
            'is_admin': 'admin' in [r.lower() for r in roles],
            'metadata': user_metadata,
            'access_token': payload.get('access_token'),
        }
        session.modified = True

        return jsonify({'ok': True, 'redirect': next_path})

    @app.after_request
    def disable_cache(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    @app.route('/')
    def index():
        """Main game page."""
        from .auth import get_current_user

        user, _error = get_current_user(request)
        if not user:
            next_path = request.full_path
            if next_path.endswith('?'):
                next_path = next_path[:-1]
            return _login_redirect(next_path or '/')

        # Always start a fresh game on page load to avoid stale history.
        _reset_game_session()
        session['server_start_id'] = app.config['SERVER_START_ID']
        game = Game()
        session['game'] = game.to_dict()

        return render_template(
            'game.html',
            game=game,
            debug_ui=app.config['DEBUG_UI'],
            show_game_controls=True,
            active_nav='game'
        )

    @app.route('/review')
    def review():
        """Review finished games."""
        from .auth import get_current_user

        user, _error = get_current_user(request)
        if not user:
            next_path = request.full_path
            if next_path.endswith('?'):
                next_path = next_path[:-1]
            return _login_redirect(next_path or '/review')

        game = Game()
        return render_template(
            'review.html',
            game=game,
            debug_ui=app.config['DEBUG_UI'],
            show_game_controls=False,
            active_nav='review'
        )

    @app.route('/resume/<string:game_id>')
    def resume_game(game_id: str):
        """Resume an unfinished game."""
        from .auth import get_current_user
        from .storage import get_game, StorageError

        user, _error = get_current_user(request)
        if not user:
            next_path = request.full_path
            if next_path.endswith('?'):
                next_path = next_path[:-1]
            return _login_redirect(next_path or f'/resume/{game_id}')

        try:
            record = get_game(game_id, user.id)
        except StorageError:
            abort(500)

        if not record:
            abort(404)

        game_state = record.get('game_state') or {}
        try:
            game = Game.from_dict(game_state)
        except Exception:
            abort(400)

        session['game'] = game.to_dict()
        session['server_start_id'] = app.config['SERVER_START_ID']
        session.modified = True

        return render_template(
            'game.html',
            game=game,
            debug_ui=app.config['DEBUG_UI'],
            show_game_controls=True,
            active_nav='game'
        )

    @app.route('/leaderboard')
    def leaderboard():
        """Leaderboard view."""
        from .auth import get_current_user

        user, _error = get_current_user(request)
        if not user:
            next_path = request.full_path
            if next_path.endswith('?'):
                next_path = next_path[:-1]
            return _login_redirect(next_path or '/leaderboard')

        return render_template(
            'leaderboard.html',
            debug_ui=app.config['DEBUG_UI'],
            show_game_controls=False,
            active_nav='leaderboard'
        )

    @app.route('/new-game', methods=['POST'])
    def new_game():
        """Start a new game."""
        _user, error = _require_auth()
        if error:
            return error

        _reset_game_session()
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
        _user, error = _require_auth()
        if error:
            return error

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

        _store_game_state(game)

        return jsonify(result)

    @app.route('/ai-move', methods=['POST'])
    def ai_move():
        """Make an AI move if it's AI's turn."""
        _user, error = _require_auth()
        if error:
            return error

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

        _store_game_state(game)
        return jsonify(result)

    @app.route('/legal-moves', methods=['POST'])
    def get_legal_moves():
        """Get legal moves for a piece."""
        _user, error = _require_auth()
        if error:
            return error

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
        _user, error = _require_auth()
        if error:
            return error

        if session.get('server_start_id') != app.config['SERVER_START_ID']:
            _reset_game_session()
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
        _user, error = _require_auth()
        if error:
            return error

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
        _user, error = _require_auth()
        if error:
            return error

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

        _store_game_state(game)

        return jsonify(result)

    @app.route('/resign', methods=['POST'])
    def resign():
        """Handle player resignation."""
        _user, error = _require_auth()
        if error:
            return error

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

        _store_game_state(game)

        return jsonify(result)

    @app.route('/timeout', methods=['POST'])
    def timeout():
        """Handle player timeout."""
        _user, error = _require_auth()
        if error:
            return error

        data = request.get_json(silent=True) or {}
        color = data.get('color')
        if color not in {'white', 'black'}:
            return jsonify({
                'success': False,
                'message': 'Invalid timeout color'
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

        game = Game.from_dict(session['game'])
        result = game.timeout(color)

        session['game'] = game.to_dict()
        session.modified = True

        _store_game_state(game)

        result['game_state'] = game.to_dict()
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


# ASGI application for uvicorn/ASGI servers
def create_asgi_app():
    """Create ASGI-wrapped Flask application for deployment behind ASGI servers."""
    flask_app = create_app()
    return WsgiToAsgi(flask_app)


# Default ASGI app instance for uvicorn target: chess_web.app:asgi_app
asgi_app = create_asgi_app()


# For development
if __name__ == '__main__':
    main()
