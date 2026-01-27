"""Simple chess AI helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Optional, Tuple

from .pieces import Pawn, Knight, Bishop, Rook, Queen, King

Move = Tuple[Tuple[int, int], Tuple[int, int]]


@dataclass(frozen=True)
class MoveChoice:
    move: Move
    score: float


PIECE_VALUES = {
    Pawn: 1.0,
    Knight: 3.0,
    Bishop: 3.25,
    Rook: 5.0,
    Queen: 9.0,
    King: 0.0,
}


def choose_ai_move(game) -> Optional[Move]:
    """Pick a move using a shallow minimax evaluation."""
    if game.game_over:
        return None

    ai_color = game.ai_color
    if game.current_turn != ai_color:
        return None

    moves = _collect_legal_moves(game, ai_color)
    if not moves:
        return None

    best_moves: List[MoveChoice] = []
    best_score: Optional[float] = None
    snapshot = game.to_dict()

    for move in moves:
        simulated = _simulate_move(game.__class__, snapshot, move)
        if simulated is None:
            continue

        score = minimax(simulated, depth=1, maximizing=False, ai_color=ai_color,
                        alpha=-math.inf, beta=math.inf)
        if best_score is None or score > best_score:
            best_score = score
            best_moves = [MoveChoice(move=move, score=score)]
        elif score == best_score:
            best_moves.append(MoveChoice(move=move, score=score))

    return random.choice(best_moves or [MoveChoice(move=random.choice(moves), score=0.0)]).move


def minimax(game, depth: int, maximizing: bool, ai_color: str,
            alpha: float, beta: float) -> float:
    """Depth-limited minimax with alpha-beta pruning."""
    if game.game_over or depth == 0:
        return evaluate_terminal(game, ai_color)

    current_color = game.current_turn
    moves = _collect_legal_moves(game, current_color)
    if not moves:
        return evaluate_terminal(game, ai_color)

    snapshot = game.to_dict()

    if maximizing:
        value = -math.inf
        for move in moves:
            simulated = _simulate_move(game.__class__, snapshot, move)
            if simulated is None:
                continue
            value = max(value, minimax(simulated, depth - 1, False, ai_color, alpha, beta))
            alpha = max(alpha, value)
            if beta <= alpha:
                break
        return value

    value = math.inf
    for move in moves:
        simulated = _simulate_move(game.__class__, snapshot, move)
        if simulated is None:
            continue
        value = min(value, minimax(simulated, depth - 1, True, ai_color, alpha, beta))
        beta = min(beta, value)
        if beta <= alpha:
            break
    return value


def evaluate_position(game, ai_color: str) -> float:
    """Simple material + mobility + check evaluation."""
    opponent = 'black' if ai_color == 'white' else 'white'
    material = _material_score(game, ai_color) - _material_score(game, opponent)
    mobility = _mobility_score(game, ai_color) - _mobility_score(game, opponent)
    check_bonus = 0.5 if game.board.is_in_check(opponent) else 0.0
    check_penalty = -0.6 if game.board.is_in_check(ai_color) else 0.0
    return material + (0.05 * mobility) + check_bonus + check_penalty


def evaluate_terminal(game, ai_color: str) -> float:
    """Return a large score for terminal outcomes, else fallback to evaluation."""
    if game.game_over:
        if game.winner == ai_color:
            return 10_000.0
        if game.winner is None:
            return 0.0
        return -10_000.0
    return evaluate_position(game, ai_color)


def _material_score(game, color: str) -> float:
    score = 0.0
    for row in range(8):
        for col in range(8):
            piece = game.board.get_piece(row, col)
            if piece and piece.color == color:
                for piece_type, value in PIECE_VALUES.items():
                    if isinstance(piece, piece_type):
                        score += value
                        break
    return score


def _mobility_score(game, color: str) -> int:
    total = 0
    for row in range(8):
        for col in range(8):
            piece = game.board.get_piece(row, col)
            if piece and piece.color == color:
                total += len(game.board.get_legal_moves((row, col)))
    return total


def _collect_legal_moves(game, color: str) -> List[Move]:
    moves: List[Move] = []
    for row in range(8):
        for col in range(8):
            piece = game.board.get_piece(row, col)
            if piece and piece.color == color:
                for move in game.board.get_legal_moves((row, col)):
                    moves.append(((row, col), move))
    return moves


def _simulate_move(game_class, snapshot: dict, move: Move):
    simulated = game_class.from_dict(snapshot)
    from_pos, to_pos = move
    result = simulated.make_move(from_pos, to_pos, 'queen')
    if not result.get('success'):
        return None
    return simulated
