# Chess Web Application

A fully-functional web-based chess game built with Python Flask and Jinja templates.

## Features

- Complete chess rules implementation including:
  - All piece movements (Pawn, Rook, Knight, Bishop, Queen, King)
  - Check and checkmate detection
  - Stalemate detection
  - **Special moves:**
    - Castling (kingside and queenside)
    - En passant capture
    - Pawn promotion with piece selection modal
  - **Draw conditions:**
    - Threefold repetition
    - Fifty-move rule
    - Insufficient material
  - Legal move validation (prevents moving into check)
  - Move history tracking with algebraic notation
  - Captured pieces display

- Modern web interface:
  - Interactive chessboard with click-to-move
  - Visual indicators for legal moves with highlights
  - Piece selection modal for pawn promotion
  - Real-time game status updates
  - Responsive design for mobile and desktop
  - Beautiful gradient background with CSS animations
  - Capture animations and move highlights

## Project Structure

```
chess-web/
├── src/
│   └── chess_web/
│       ├── __init__.py
│       ├── app.py                 # Flask application and routes
│       ├── models/
│       │   ├── __init__.py
│       │   ├── pieces.py          # Chess piece classes
│       │   ├── board.py           # Board representation
│       │   └── game.py            # Game state manager
│       ├── templates/
│       │   ├── base.html          # Base template
│       │   └── game.html          # Game page
│       └── static/
│           ├── css/
│           │   └── style.css      # Styles
│           └── js/
│               └── chess.js       # Client-side logic
├── tests/
├── pyproject.toml
└── README.md
```

## Installation

Install dependencies using uv:

```bash
uv sync
```

Or install in editable mode:

```bash
uv pip install -e .
```

## Running the Application

### Quick Start (Recommended)

Using uv run:

```bash
uv run chess-web
```

Or run directly:

```bash
uv run python run.py
```

### Alternative Methods

Using Flask CLI:

```bash
uv run flask --app src.chess_web.app run --debug
```

Or run the module directly:

```bash
uv run python -m src.chess_web.app
```

The application will start at http://127.0.0.1:5000

## How to Play

1. White moves first
2. Click on a piece to select it
3. Valid moves will be highlighted
4. Click on a highlighted square to move
5. The game will notify you of check, checkmate, or stalemate
6. Use "New Game" to start over
7. Use "Resign" to forfeit the current game

## Technology Stack

- **Backend**: Python 3.13+ with Flask
- **Templating**: Jinja2
- **Frontend**: Vanilla JavaScript (no frameworks)
- **Styling**: CSS3 with responsive design
- **Session Management**: Flask-Session

## Future Enhancements

- Undo/redo moves
- Game save/load functionality
- AI opponent with difficulty levels
- Multiplayer with WebSockets
- Timer/clock functionality
- PGN export/import
- Drag and drop piece movement
- Move hints and analysis
- Opening book database

## License

MIT License
