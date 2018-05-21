"""WebSocket event server.

Set DEBUG=1 in environment for debug mode.
"""

from flask_socketio import SocketIO, emit, disconnect
import functools
from flask_login import current_user
from flask import redirect, _request_ctx_stack, request
import logging
from socketio_pg import PubSub
import eventlet


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class SocketServer():
    def __init__(self, app, dsn, enable_test_page=False, port=3030, test=False):
        """Create websocket server for application."""
        self.AUTH_REQUIRED = False  # for development/testing
        self.app = app
        self.dsn = dsn
        self.socketio = SocketIO(self.app)
        self.pubsub = PubSub(app=self.app, dsn=dsn)
        self.port = port
        self.test = test
        self.listen_gthreads = dict()  # map of sid => [list of listen green threads]
        self.subscriptions = dict()  # map of sid => [list of subscriptions]

        @self.app.login_manager.request_loader
        def authenticate_user(request_):
            """This is a hook where you can perform user authentication if you want.

            You can get args from request_, for example authenticating a JWT access token.
            If you return a user here, it will be set as current_user for the session.
            See flask_login for more details.
            """
            return request.remote_addr

        def authenticated_only(f):
            """Require authentication to access socket resource."""
            @functools.wraps(f)
            def wrapped(*args, **kwargs):
                """Authenticate and redirect to avatar URL."""
                if self.AUTH_REQUIRED and (not current_user or not current_user.is_authenticated):
                    log.info("disconnecting unauthenticated websocket connection")
                    disconnect()
                else:
                    return f(*args, **kwargs)
            return wrapped

        @self.socketio.on('connect')
        @authenticated_only
        def handle_client_connect():
            """Handle client connected."""
            log.warning(f"Client {current_user} connected")
            self.listen_gthreads[request.sid] = []
            self.subscriptions[request.sid] = []
            emit('server_hello', {'client': str(current_user)})

        @self.socketio.on('disconnect')
        def handle_client_disconnect():
            """Handle client disconnected.

            Remove subscription threads.
            """
            for lgt in self.listen_gthreads[request.sid]:
                eventlet.kill(lgt)
            for sub in self.subscriptions[request.sid]:
                self.pubsub.unsubscribe(sub)
            log.info(f"Client {current_user} disconnected")

        @self.socketio.on('subscribe')
        @authenticated_only
        def handle_client_subscribe(data):
            """Handle client subscribing to a channel."""
            channel = data['channel']

            # make a queue to receive events from pubsub
            q = eventlet.Queue(maxsize=20)

            # save request context for eventlet ctx switch
            req_ctx_stack = _request_ctx_stack
            req_ctx = req_ctx_stack.top.copy()

            def emit_green(q, req_ctx):
                """Wait for events on the queue and emit them to client."""
                while 1:
                    n = q.get()  # block on waiting for item from queue
                    req_ctx.push()  # restore request context
                    emit('event', n)  # send event to client (has channel and payload fields)
                    req_ctx.pop()  # done with request context

            # subscribe and queue emit callbacks, async
            subscription = self.pubsub.subscribe(channel, q)
            listen_gthread = eventlet.spawn(emit_green, q, req_ctx)
            self.listen_gthreads[request.sid].append(listen_gthread)
            self.subscriptions[request.sid].append(subscription)
            log.info(f"Client {current_user} subscribed to {channel}")
            emit('subscribed', {'channel': channel})

        if enable_test_page:
            @self.app.route('/socket-test')
            def socket_test():
                """Show socket test page."""
                return redirect('/static/test.html')

        if self.test:
            # endpoints for testing
            @self.socketio.on('test_pub')
            def test_pub(data):
                """Publish message."""
                if 'channel' not in data:
                    return self.client_error("Channel required")
                channel = data['channel']
                payload = data['payload'] if 'payload' in data else None
                self.pubsub.publish(data['channel'], payload)
                emit('published', {'channel': channel})

    def client_error(self, message):
        """Emit an error message."""
        emit('error', {'message': message})

    def run(self):
        """Run the server, if not launched via gunicorn etc."""
        self.socketio.run(self.app, port=self.port)

    def shutdown(self):
        """Terminate connections and server."""
        self.pubsub.disconnect()
