"""Auth helper endpoints."""

from flask import request
from flask_restx import Namespace, Resource, fields

from ..auth import get_current_user

ns = Namespace('auth', description='Authentication helpers')

user_model = ns.model('AuthUser', {
    'id': fields.String(description='User id'),
    'email': fields.String(description='User email'),
    'name': fields.String(description='Display name'),
})

me_response = ns.model('MeResponse', {
    'user': fields.Nested(user_model, description='Authenticated user')
})


@ns.route('/me')
class Me(Resource):
    @ns.doc('auth_me')
    @ns.marshal_with(me_response)
    @ns.response(200, 'Authenticated user')
    @ns.response(401, 'Unauthorized')
    def get(self):
        """Return the current authenticated user."""
        user, error = get_current_user(request)
        if not user:
            ns.abort(401, error or 'Unauthorized')
        return {'user': user.to_dict()}
