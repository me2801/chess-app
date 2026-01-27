"""Chess piece classes and movement logic."""

from typing import List, Tuple, Optional


class Piece:
    """Base class for all chess pieces."""

    def __init__(self, color: str, position: Tuple[int, int]):
        """
        Initialize a chess piece.

        Args:
            color: 'white' or 'black'
            position: (row, col) tuple where row and col are 0-7
        """
        self.color = color
        self.position = position
        self.has_moved = False

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        """
        Get all possible moves for this piece (without checking for check).

        Args:
            board: The current board state

        Returns:
            List of (row, col) tuples representing valid destination squares
        """
        raise NotImplementedError("Subclasses must implement get_possible_moves")

    def to_dict(self) -> dict:
        """Convert piece to dictionary for JSON serialization."""
        return {
            'type': self.__class__.__name__.lower(),
            'color': self.color,
            'position': self.position,
            'has_moved': self.has_moved
        }

    def get_symbol(self) -> str:
        """Get Unicode symbol for the piece."""
        raise NotImplementedError("Subclasses must implement get_symbol")

    def _is_valid_position(self, row: int, col: int) -> bool:
        """Check if position is within board bounds."""
        return 0 <= row < 8 and 0 <= col < 8

    def _is_enemy(self, piece: Optional['Piece']) -> bool:
        """Check if a piece is an enemy."""
        return piece is not None and piece.color != self.color

    def _is_friendly(self, piece: Optional['Piece']) -> bool:
        """Check if a piece is friendly."""
        return piece is not None and piece.color == self.color


class Pawn(Piece):
    """Pawn piece."""

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        moves = []
        row, col = self.position
        direction = -1 if self.color == 'white' else 1

        # Move forward one square
        new_row = row + direction
        if self._is_valid_position(new_row, col) and board.get_piece(new_row, col) is None:
            moves.append((new_row, col))

            # Move forward two squares from starting position
            if not self.has_moved:
                new_row2 = row + 2 * direction
                if board.get_piece(new_row2, col) is None:
                    moves.append((new_row2, col))

        # Capture diagonally
        for dc in [-1, 1]:
            new_row = row + direction
            new_col = col + dc
            if self._is_valid_position(new_row, new_col):
                piece = board.get_piece(new_row, new_col)
                if self._is_enemy(piece):
                    moves.append((new_row, new_col))

        # En passant capture
        if hasattr(board, 'en_passant_target') and board.en_passant_target:
            en_row, en_col = board.en_passant_target
            if row + direction == en_row and abs(col - en_col) == 1:
                moves.append((en_row, en_col))

        return moves

    def get_symbol(self) -> str:
        return '♙' if self.color == 'white' else '♟'


class Rook(Piece):
    """Rook piece."""

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        moves = []
        row, col = self.position

        # Horizontal and vertical directions
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        for dr, dc in directions:
            for i in range(1, 8):
                new_row = row + dr * i
                new_col = col + dc * i

                if not self._is_valid_position(new_row, new_col):
                    break

                piece = board.get_piece(new_row, new_col)
                if piece is None:
                    moves.append((new_row, new_col))
                elif self._is_enemy(piece):
                    moves.append((new_row, new_col))
                    break
                else:
                    break

        return moves

    def get_symbol(self) -> str:
        return '♖' if self.color == 'white' else '♜'


class Knight(Piece):
    """Knight piece."""

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        moves = []
        row, col = self.position

        # All possible knight moves
        knight_moves = [
            (-2, -1), (-2, 1), (-1, -2), (-1, 2),
            (1, -2), (1, 2), (2, -1), (2, 1)
        ]

        for dr, dc in knight_moves:
            new_row = row + dr
            new_col = col + dc

            if self._is_valid_position(new_row, new_col):
                piece = board.get_piece(new_row, new_col)
                if piece is None or self._is_enemy(piece):
                    moves.append((new_row, new_col))

        return moves

    def get_symbol(self) -> str:
        return '♘' if self.color == 'white' else '♞'


class Bishop(Piece):
    """Bishop piece."""

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        moves = []
        row, col = self.position

        # Diagonal directions
        directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        for dr, dc in directions:
            for i in range(1, 8):
                new_row = row + dr * i
                new_col = col + dc * i

                if not self._is_valid_position(new_row, new_col):
                    break

                piece = board.get_piece(new_row, new_col)
                if piece is None:
                    moves.append((new_row, new_col))
                elif self._is_enemy(piece):
                    moves.append((new_row, new_col))
                    break
                else:
                    break

        return moves

    def get_symbol(self) -> str:
        return '♗' if self.color == 'white' else '♝'


class Queen(Piece):
    """Queen piece."""

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        moves = []
        row, col = self.position

        # Horizontal, vertical, and diagonal directions
        directions = [
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]

        for dr, dc in directions:
            for i in range(1, 8):
                new_row = row + dr * i
                new_col = col + dc * i

                if not self._is_valid_position(new_row, new_col):
                    break

                piece = board.get_piece(new_row, new_col)
                if piece is None:
                    moves.append((new_row, new_col))
                elif self._is_enemy(piece):
                    moves.append((new_row, new_col))
                    break
                else:
                    break

        return moves

    def get_symbol(self) -> str:
        return '♕' if self.color == 'white' else '♛'


class King(Piece):
    """King piece."""

    def get_possible_moves(self, board: 'Board') -> List[Tuple[int, int]]:
        moves = []
        row, col = self.position

        # All adjacent squares
        directions = [
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]

        for dr, dc in directions:
            new_row = row + dr
            new_col = col + dc

            if self._is_valid_position(new_row, new_col):
                piece = board.get_piece(new_row, new_col)
                if piece is None or self._is_enemy(piece):
                    moves.append((new_row, new_col))

        # Castling - only check if we haven't moved yet
        # The legal move check will filter out castling if we're in check
        if not self.has_moved:
            enemy_color = 'black' if self.color == 'white' else 'white'

            # Kingside castling
            rook_kingside = board.get_piece(row, 7)
            if (isinstance(rook_kingside, Rook) and not rook_kingside.has_moved and
                board.get_piece(row, 5) is None and board.get_piece(row, 6) is None):
                # Note: We add the move here, and get_legal_moves will filter out
                # if current position is in check or if we move through check
                moves.append((row, 6))

            # Queenside castling
            rook_queenside = board.get_piece(row, 0)
            if (isinstance(rook_queenside, Rook) and not rook_queenside.has_moved and
                board.get_piece(row, 1) is None and board.get_piece(row, 2) is None and
                board.get_piece(row, 3) is None):
                moves.append((row, 2))

        return moves

    def get_symbol(self) -> str:
        return '♔' if self.color == 'white' else '♚'
