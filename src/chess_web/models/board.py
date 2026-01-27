"""Chess board representation and logic."""

from typing import Optional, Tuple, List
from .pieces import Piece, Pawn, Rook, Knight, Bishop, Queen, King


class Board:
    """Represents a chess board and handles piece placement."""

    def __init__(self):
        """Initialize an 8x8 chess board."""
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.en_passant_target = None  # Track en passant opportunity
        self._initialize_pieces()

    def _initialize_pieces(self):
        """Set up pieces in their starting positions."""
        # Pawns
        for col in range(8):
            self.board[1][col] = Pawn('black', (1, col))
            self.board[6][col] = Pawn('white', (6, col))

        # Rooks
        self.board[0][0] = Rook('black', (0, 0))
        self.board[0][7] = Rook('black', (0, 7))
        self.board[7][0] = Rook('white', (7, 0))
        self.board[7][7] = Rook('white', (7, 7))

        # Knights
        self.board[0][1] = Knight('black', (0, 1))
        self.board[0][6] = Knight('black', (0, 6))
        self.board[7][1] = Knight('white', (7, 1))
        self.board[7][6] = Knight('white', (7, 6))

        # Bishops
        self.board[0][2] = Bishop('black', (0, 2))
        self.board[0][5] = Bishop('black', (0, 5))
        self.board[7][2] = Bishop('white', (7, 2))
        self.board[7][5] = Bishop('white', (7, 5))

        # Queens
        self.board[0][3] = Queen('black', (0, 3))
        self.board[7][3] = Queen('white', (7, 3))

        # Kings
        self.board[0][4] = King('black', (0, 4))
        self.board[7][4] = King('white', (7, 4))

    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        """
        Get the piece at the given position.

        Args:
            row: Row index (0-7)
            col: Column index (0-7)

        Returns:
            Piece object or None if empty
        """
        if 0 <= row < 8 and 0 <= col < 8:
            return self.board[row][col]
        return None

    def set_piece(self, row: int, col: int, piece: Optional[Piece]):
        """
        Set a piece at the given position.

        Args:
            row: Row index (0-7)
            col: Column index (0-7)
            piece: Piece object or None to clear
        """
        if 0 <= row < 8 and 0 <= col < 8:
            self.board[row][col] = piece
            if piece:
                piece.position = (row, col)

    def move_piece(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """
        Move a piece from one position to another.

        Args:
            from_pos: (row, col) of the piece to move
            to_pos: (row, col) of the destination

        Returns:
            True if move was successful, False otherwise
        """
        from_row, from_col = from_pos
        to_row, to_col = to_pos

        piece = self.get_piece(from_row, from_col)
        if piece is None:
            return False

        # Move the piece
        self.set_piece(to_row, to_col, piece)
        self.set_piece(from_row, from_col, None)
        piece.has_moved = True

        return True

    def find_king(self, color: str) -> Optional[Tuple[int, int]]:
        """
        Find the position of the king for the given color.

        Args:
            color: 'white' or 'black'

        Returns:
            (row, col) tuple or None if not found
        """
        for row in range(8):
            for col in range(8):
                piece = self.get_piece(row, col)
                if isinstance(piece, King) and piece.color == color:
                    return (row, col)
        return None

    def is_square_attacked(self, position: Tuple[int, int], by_color: str) -> bool:
        """
        Check if a square is attacked by any piece of the given color.

        Args:
            position: (row, col) to check
            by_color: Color of the attacking pieces

        Returns:
            True if the square is under attack
        """
        for row in range(8):
            for col in range(8):
                piece = self.get_piece(row, col)
                if piece and piece.color == by_color:
                    possible_moves = piece.get_possible_moves(self)
                    if position in possible_moves:
                        return True
        return False

    def is_in_check(self, color: str) -> bool:
        """
        Check if the king of the given color is in check.

        Args:
            color: 'white' or 'black'

        Returns:
            True if the king is in check
        """
        king_pos = self.find_king(color)
        if king_pos is None:
            return False

        enemy_color = 'black' if color == 'white' else 'white'
        return self.is_square_attacked(king_pos, enemy_color)

    def get_legal_moves(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Get all legal moves for a piece (moves that don't leave king in check).

        Args:
            position: (row, col) of the piece

        Returns:
            List of (row, col) tuples
        """
        row, col = position
        piece = self.get_piece(row, col)
        if piece is None:
            return []

        possible_moves = piece.get_possible_moves(self)
        legal_moves = []

        # Import King here to avoid circular import issues
        from .pieces import King

        for move in possible_moves:
            move_row, move_col = move

            # Special validation for castling
            if isinstance(piece, King) and abs(move_col - col) == 2:
                # This is a castling move
                enemy_color = 'black' if piece.color == 'white' else 'white'

                # Check if king is currently in check (can't castle out of check)
                if self.is_in_check(piece.color):
                    continue

                # Check if king passes through or ends on an attacked square
                if move_col > col:  # Kingside
                    if (self.is_square_attacked((row, col + 1), enemy_color) or
                        self.is_square_attacked((row, col + 2), enemy_color)):
                        continue
                else:  # Queenside
                    if (self.is_square_attacked((row, col - 1), enemy_color) or
                        self.is_square_attacked((row, col - 2), enemy_color)):
                        continue

                legal_moves.append(move)
                continue

            # Simulate the move
            captured_piece = self.get_piece(move_row, move_col)
            original_pos = piece.position

            self.set_piece(move_row, move_col, piece)
            self.set_piece(row, col, None)

            # Check if this move leaves the king in check
            if not self.is_in_check(piece.color):
                legal_moves.append(move)

            # Undo the move
            self.set_piece(row, col, piece)
            self.set_piece(move_row, move_col, captured_piece)
            piece.position = original_pos

        return legal_moves

    def has_legal_moves(self, color: str) -> bool:
        """
        Check if the given color has any legal moves.

        Args:
            color: 'white' or 'black'

        Returns:
            True if there are legal moves available
        """
        for row in range(8):
            for col in range(8):
                piece = self.get_piece(row, col)
                if piece and piece.color == color:
                    if len(self.get_legal_moves((row, col))) > 0:
                        return True
        return False

    def to_dict(self) -> dict:
        """
        Convert board state to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the board
        """
        board_dict = []
        for row in range(8):
            row_dict = []
            for col in range(8):
                piece = self.get_piece(row, col)
                row_dict.append(piece.to_dict() if piece else None)
            board_dict.append(row_dict)
        return {
            'board': board_dict,
            'en_passant_target': list(self.en_passant_target) if self.en_passant_target else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Board':
        """
        Create a board from dictionary representation.

        Args:
            data: Dictionary containing board state

        Returns:
            Board instance
        """
        board = cls.__new__(cls)
        board.board = [[None for _ in range(8)] for _ in range(8)]

        piece_classes = {
            'pawn': Pawn,
            'rook': Rook,
            'knight': Knight,
            'bishop': Bishop,
            'queen': Queen,
            'king': King
        }

        for row in range(8):
            for col in range(8):
                piece_data = data['board'][row][col]
                if piece_data:
                    piece_class = piece_classes[piece_data['type']]
                    piece = piece_class(piece_data['color'], (row, col))
                    piece.has_moved = piece_data.get('has_moved', False)
                    board.board[row][col] = piece

        # Restore en passant target
        en_passant = data.get('en_passant_target')
        board.en_passant_target = tuple(en_passant) if en_passant else None

        return board
