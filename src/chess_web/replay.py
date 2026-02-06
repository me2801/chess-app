"""Replay helpers for reviewing finished games."""

from typing import List, Dict, Any

from .models import Game


def build_replay_states(move_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a list of game states from the initial position through each move."""
    game = Game()
    states = [game.to_dict()]

    for move in move_history:
        from_pos = tuple(move.get('from', (0, 0)))
        to_pos = tuple(move.get('to', (0, 0)))
        promotion = move.get('promotion') or 'queen'
        game.make_move(from_pos, to_pos, promotion)
        states.append(game.to_dict())

    return states
