"""Chess game state management."""

from typing import Optional, Tuple, List
import copy
import uuid

from .ai import choose_ai_move
from .board import Board
from .pieces import Pawn, Queen, Rook, Bishop, Knight, King


class Game:
    """Manages the chess game state and rules."""

    def __init__(self):
        """Initialize a new chess game."""
        self.game_id = uuid.uuid4().hex
        self.board = Board()
        self.current_turn = 'white'
        self.move_history = []
        self.captured_pieces = {'white': [], 'black': []}
        self.game_over = False
        self.winner = None
        self.status_message = "White's turn"
        self.en_passant_target = None  # Track en passant opportunity
        self.halfmove_clock = 0  # For fifty-move rule
        self.position_history = []  # For threefold repetition
        self.ai_enabled = True
        self.ai_color = 'black'

    def make_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                  promotion_piece: str = 'queen') -> dict:
        """
        Attempt to make a move.

        Args:
            from_pos: (row, col) of the piece to move
            to_pos: (row, col) of the destination
            promotion_piece: Type of piece to promote pawn to (queen, rook, bishop, knight)

        Returns:
            Dictionary with success status and message
        """
        if self.game_over:
            return {
                'success': False,
                'message': 'Game is over',
                'game_over': True
            }

        from_row, from_col = from_pos
        to_row, to_col = to_pos

        # Get the piece
        piece = self.board.get_piece(from_row, from_col)
        if piece is None:
            return {'success': False, 'message': 'No piece at that position'}

        # Check if it's the correct player's turn
        if piece.color != self.current_turn:
            return {'success': False, 'message': f"It's {self.current_turn}'s turn"}

        # Check if the move is legal
        legal_moves = self.board.get_legal_moves(from_pos)
        if to_pos not in legal_moves:
            return {'success': False, 'message': 'Illegal move'}

        # Handle en passant capture
        captured = self.board.get_piece(to_row, to_col)
        en_passant_capture = False
        if isinstance(piece, Pawn) and to_pos == self.en_passant_target:
            # En passant capture - remove the captured pawn
            capture_row = from_row
            capture_col = to_col
            captured = self.board.get_piece(capture_row, capture_col)
            self.board.set_piece(capture_row, capture_col, None)
            en_passant_capture = True

        if captured:
            self.captured_pieces[self.current_turn].append(captured)

        # Handle castling
        is_castling = False
        if isinstance(piece, King) and abs(to_col - from_col) == 2:
            is_castling = True
            # Move the rook
            if to_col > from_col:  # Kingside castling
                rook = self.board.get_piece(from_row, 7)
                self.board.move_piece((from_row, 7), (from_row, 5))
            else:  # Queenside castling
                rook = self.board.get_piece(from_row, 0)
                self.board.move_piece((from_row, 0), (from_row, 3))

        # Make the move
        self.board.move_piece(from_pos, to_pos)

        # Handle pawn promotion
        promoted = False
        if isinstance(piece, Pawn) and (to_row == 0 or to_row == 7):
            # Promote the pawn
            piece_classes = {
                'queen': Queen,
                'rook': Rook,
                'bishop': Bishop,
                'knight': Knight
            }
            new_piece_class = piece_classes.get(promotion_piece.lower(), Queen)
            new_piece = new_piece_class(piece.color, to_pos)
            self.board.set_piece(to_row, to_col, new_piece)
            promoted = True
            piece = new_piece

        # Track en passant opportunity
        self.en_passant_target = None
        self.board.en_passant_target = None
        if isinstance(piece, Pawn) and abs(to_row - from_row) == 2 and not promoted:
            # Pawn moved two squares, set en passant target
            target = ((from_row + to_row) // 2, to_col)
            self.en_passant_target = target
            self.board.en_passant_target = target

        # Update halfmove clock for fifty-move rule
        if isinstance(piece, Pawn) or captured:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Record position for threefold repetition
        position_hash = self._get_position_hash()
        self.position_history.append(position_hash)

        # Record move
        move_notation = self._get_move_notation(piece, from_pos, to_pos, captured)
        self.move_history.append({
            'from': from_pos,
            'to': to_pos,
            'piece': piece.to_dict(),
            'captured': captured.to_dict() if captured else None,
            'notation': move_notation
        })

        # Switch turns
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'

        # Check game state
        in_check = self.board.is_in_check(self.current_turn)
        has_moves = self.board.has_legal_moves(self.current_turn)

        # Check for draw conditions
        draw_by_fifty = self.halfmove_clock >= 50
        draw_by_repetition = self.position_history.count(position_hash) >= 3
        draw_by_material = self._is_insufficient_material()

        if in_check and not has_moves:
            # Checkmate
            self.game_over = True
            self.winner = 'black' if self.current_turn == 'white' else 'white'
            self.status_message = f"Checkmate! {self.winner.capitalize()} wins!"
        elif not has_moves:
            # Stalemate
            self.game_over = True
            self.status_message = "Stalemate! Game is a draw."
        elif draw_by_fifty:
            # Fifty-move rule
            self.game_over = True
            self.status_message = "Draw by fifty-move rule!"
        elif draw_by_repetition:
            # Threefold repetition
            self.game_over = True
            self.status_message = "Draw by threefold repetition!"
        elif draw_by_material:
            # Insufficient material
            self.game_over = True
            self.status_message = "Draw by insufficient material!"
        elif in_check:
            self.status_message = f"{self.current_turn.capitalize()} is in check!"
        else:
            self.status_message = f"{self.current_turn.capitalize()}'s turn"

        return {
            'success': True,
            'message': self.status_message,
            'in_check': in_check,
            'game_over': self.game_over,
            'winner': self.winner
        }

    def get_legal_moves(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Get legal moves for a piece at the given position.

        Args:
            position: (row, col) of the piece

        Returns:
            List of legal move positions
        """
        piece = self.board.get_piece(*position)
        if piece is None or piece.color != self.current_turn:
            return []

        return self.board.get_legal_moves(position)

    def resign(self, color: str) -> dict:
        """
        Resign the game.

        Args:
            color: Color of the player resigning

        Returns:
            Dictionary with game result
        """
        self.game_over = True
        self.winner = 'black' if color == 'white' else 'white'
        self.status_message = f"{color.capitalize()} resigned. {self.winner.capitalize()} wins!"

        return {
            'success': True,
            'message': self.status_message,
            'game_over': True,
            'winner': self.winner
        }

    def make_ai_move(self) -> Optional[dict]:
        """
        Make a simple AI move for the configured AI color.

        Returns:
            Result dict from make_move, or None if no AI move is available.
        """
        if not self.ai_enabled or self.game_over or self.current_turn != self.ai_color:
            return None

        ai_move = choose_ai_move(self)
        if not ai_move:
            return None

        from_pos, to_pos = ai_move
        result = self.make_move(from_pos, to_pos, 'queen')
        if result.get('success'):
            result['ai_move'] = {'from': from_pos, 'to': to_pos}
        return result

    def _get_move_notation(self, piece, from_pos: Tuple[int, int],
                          to_pos: Tuple[int, int], captured) -> str:
        """
        Get algebraic notation for a move.

        Args:
            piece: The piece being moved
            from_pos: Starting position
            to_pos: Ending position
            captured: Captured piece if any

        Returns:
            Move notation string (e.g., e4, Nf3, exd5, O-O)
        """
        from_row, from_col = from_pos
        to_row, to_col = to_pos

        # Check for castling
        if isinstance(piece, King) and abs(to_col - from_col) == 2:
            return 'O-O' if to_col > from_col else 'O-O-O'

        # Get piece symbol for notation
        class_name = piece.__class__.__name__
        if class_name == 'Knight':
            piece_symbol = 'N'
        elif class_name == 'King':
            piece_symbol = 'K'
        elif class_name == 'Queen':
            piece_symbol = 'Q'
        elif class_name == 'Rook':
            piece_symbol = 'R'
        elif class_name == 'Bishop':
            piece_symbol = 'B'
        elif class_name == 'Pawn':
            piece_symbol = ''
        else:
            piece_symbol = class_name[0].upper()

        to_file = chr(ord('a') + to_col)
        to_rank = str(8 - to_row)

        # For pawn captures, include the starting file
        if piece_symbol == '' and captured:
            from_file = chr(ord('a') + from_col)
            return f"{from_file}x{to_file}{to_rank}"

        # For other pieces
        capture_symbol = 'x' if captured else ''
        return f"{piece_symbol}{capture_symbol}{to_file}{to_rank}"

    def _get_position_hash(self) -> str:
        """
        Get a hash of the current position for threefold repetition detection.

        Returns:
            Hash string representing the position
        """
        # Create a simple hash of board state
        position_str = []
        for row in range(8):
            for col in range(8):
                piece = self.board.get_piece(row, col)
                if piece:
                    position_str.append(f"{piece.__class__.__name__[0]}{piece.color[0]}{row}{col}")
                else:
                    position_str.append("--")
        position_str.append(self.current_turn)
        return ''.join(position_str)

    def _is_insufficient_material(self) -> bool:
        """
        Check if there is insufficient material to checkmate.

        Returns:
            True if neither side can possibly checkmate
        """
        pieces = []
        for row in range(8):
            for col in range(8):
                piece = self.board.get_piece(row, col)
                if piece and not isinstance(piece, King):
                    pieces.append(piece.__class__.__name__)

        # King vs King
        if len(pieces) == 0:
            return True

        # King and Bishop vs King or King and Knight vs King
        if len(pieces) == 1:
            if pieces[0] in ['Bishop', 'Knight']:
                return True

        # King and Bishop vs King and Bishop (same color squares)
        if len(pieces) == 2:
            if pieces[0] == 'Bishop' and pieces[1] == 'Bishop':
                # Check if bishops are on same colored squares
                bishops = []
                for row in range(8):
                    for col in range(8):
                        piece = self.board.get_piece(row, col)
                        if piece and isinstance(piece, Bishop):
                            bishops.append((row + col) % 2)
                if len(bishops) == 2 and bishops[0] == bishops[1]:
                    return True

        return False

    def to_dict(self) -> dict:
        """
        Convert game state to dictionary for JSON serialization.

        Returns:
            Dictionary representation of game state
        """
        return {
            'game_id': self.game_id,
            'board': self.board.to_dict(),
            'current_turn': self.current_turn,
            'move_history': copy.deepcopy(self.move_history),
            'captured_pieces': {
                'white': [p.to_dict() for p in self.captured_pieces['white']],
                'black': [p.to_dict() for p in self.captured_pieces['black']]
            },
            'game_over': self.game_over,
            'winner': self.winner,
            'status_message': self.status_message,
            'en_passant_target': list(self.en_passant_target) if self.en_passant_target else None,
            'halfmove_clock': self.halfmove_clock,
            'position_history': copy.deepcopy(self.position_history),
            'ai_enabled': self.ai_enabled,
            'ai_color': self.ai_color
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Game':
        """
        Create a game from dictionary representation.

        Args:
            data: Dictionary containing game state

        Returns:
            Game instance
        """
        game = cls.__new__(cls)
        game.game_id = data.get('game_id', uuid.uuid4().hex)
        game.board = Board.from_dict(data['board'])
        game.current_turn = data['current_turn']
        game.move_history = copy.deepcopy(data.get('move_history', []))
        raw_captured = data.get('captured_pieces', {'white': [], 'black': []})
        game.captured_pieces = {
            'white': cls._deserialize_captured(raw_captured.get('white', [])),
            'black': cls._deserialize_captured(raw_captured.get('black', []))
        }
        game.game_over = data['game_over']
        game.winner = data.get('winner')
        game.status_message = data['status_message']

        # Restore en passant target
        en_passant = data.get('en_passant_target')
        game.en_passant_target = tuple(en_passant) if en_passant else None

        # Restore draw condition tracking
        game.halfmove_clock = data.get('halfmove_clock', 0)
        game.position_history = copy.deepcopy(data.get('position_history', []))
        game.ai_enabled = data.get('ai_enabled', True)
        game.ai_color = data.get('ai_color', 'black')

        return game

    @staticmethod
    def _deserialize_captured(items):
        """Convert captured piece dicts back into Piece objects."""
        piece_classes = {
            'pawn': Pawn,
            'rook': Rook,
            'knight': Knight,
            'bishop': Bishop,
            'queen': Queen,
            'king': King
        }

        converted = []
        for item in items:
            if hasattr(item, 'to_dict'):
                converted.append(item)
                continue
            if not isinstance(item, dict):
                continue
            piece_type = item.get('type')
            piece_class = piece_classes.get(piece_type)
            if not piece_class:
                continue
            position = tuple(item.get('position', (0, 0)))
            piece = piece_class(item.get('color', 'white'), position)
            piece.has_moved = item.get('has_moved', False)
            converted.append(piece)
        return converted
