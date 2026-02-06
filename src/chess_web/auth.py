"""Supabase authentication helpers using server-side session."""

from dataclasses import dataclass
from typing import Optional, Tuple

from flask import session


@dataclass
class AuthUser:
    """Normalized authenticated user."""

    id: str
    email: Optional[str]
    name: Optional[str]
    metadata: dict

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'metadata': self.metadata
        }


def get_current_user(_request=None) -> Tuple[Optional[AuthUser], Optional[str]]:
    """Return the authenticated user for this request."""
    auth = session.get('auth') or {}
    user_id = auth.get('user_id')
    if not user_id:
        return None, 'Unauthorized'

    metadata = auth.get('metadata') or {}
    return AuthUser(
        id=user_id,
        email=auth.get('email'),
        name=auth.get('name'),
        metadata=metadata
    ), None


def clear_session() -> None:
    """Clear auth session."""
    session.pop('auth', None)
