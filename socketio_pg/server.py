"""WebSocket event server."""

# set up PYTHONPATH
import os
import sys
ABSOLUTE_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ABSOLUTE_PROJECT_ROOT not in sys.path:
    sys.path.insert(0, ABSOLUTE_PROJECT_ROOT)

import eventlet
eventlet.monkey_patch()

import logging
from socketio_pg.websocket import SocketServer
from socketio_pg.app import create_app

log = logging.getLogger(__name__)

# init app and websocket server
app = create_app()
dsn = app.config['SQLALCHEMY_DATABASE_URI']
server = SocketServer(app=app, dsn=dsn, enable_test_page=app.config['DEBUG'])

if __name__ == '__main__':
    server.run()
