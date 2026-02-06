"""Chess API with Swagger documentation."""

from flask import Blueprint
from flask_restx import Api

# Create the main API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Create the API with Swagger documentation
api = Api(
    api_bp,
    version='1.0',
    title='Chess Game API',
    description='RESTful API for the Chess Game application',
    doc='/docs',
    authorizations={
        'session': {
            'type': 'apiKey',
            'in': 'cookie',
            'name': 'session'
        }
    }
)

# Import and register namespaces
from .game import ns as game_ns
from .moves import ns as moves_ns
from .persistence import ns as persistence_ns
from .auth import ns as auth_ns
from .records import ns as records_ns

api.add_namespace(game_ns)
api.add_namespace(moves_ns)
api.add_namespace(persistence_ns)
api.add_namespace(auth_ns)
api.add_namespace(records_ns)
