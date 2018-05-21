"""PubSub app factory."""

from flask import Flask
import os
from flask_login import LoginManager
import logging

log = logging.getLogger(__name__)
login_manager = LoginManager()


def create_app():
    """Create a pubsub application.

    http://flask.pocoo.org/docs/0.12/patterns/appfactories/
    """
    abs_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(
        __name__,
        instance_path=abs_project_root,
        instance_relative_config=True,
    )

    setup_config(app)
    setup_db(app)
    login_manager.init_app(app)

    return app


def setup_config(app):
    """Load configuration from defaults then local overrides."""
    app.config.from_pyfile('config.py', silent=False)
    # optional local config
    app.config.from_pyfile('local.cfg', silent=True)


def setup_db(app):
    """Connect to database."""
    dsn = app.config.get('SQLALCHEMY_DATABASE_URI')
    if not dsn:
        raise Exception("DATABASE_URL is missing. Please create a local.cfg or define it in the environment.")

    from socketio_pg.model import db
    db.init_app(app)
