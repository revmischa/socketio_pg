"""Test connecting to a live pubsub socketio server.

You must have a PubSub server running with the address set in TEST_PUBSUB_SERVER_ADDR.

Run with: TEST_PUBSUB_SERVER_ADDR=localhost pytest socketio_pg/tests/test_live.py
"""

from unittest import TestCase
# import eventlet
import logging
from socketIO_client import SocketIO, BaseNamespace
import os

# enable debug logs
logging.getLogger('socketIO-client').setLevel(logging.DEBUG)
logging.basicConfig()


class PubSubTestCase(TestCase, BaseNamespace):
    def setUp(self):
        """Initialize websocket client."""
        server_addr = os.getenv('TEST_PUBSUB_SERVER_ADDR')
        server_port = os.getenv('TEST_PUBSUB_SERVER_PORT', 3030)
        if not server_addr:
            self.skipTest("TEST_PUBSUB_SERVER_ADDR not defined; skipping live tests")
            return
        self.server_addr = server_addr
        self.server_port = server_port

        self.sio_connected = False
        self.got_server_hello = False

    def on_connect(self):
        """Connected callback."""
        self.sio_connected = True
        print("CONNECTED")

    def on_disconnect(self):
        """Disconnected callback."""
        self.sio_connected = False
        print("DISCONNECTED")

# with SocketIO('localhost', 8000, LoggingNamespace) as socketIO:
#     def tearDown(self):
#         """Shut down pubsub websocket server."""
#         self.ws.shutdown()
#         super().tearDown()

    def test_subscribe_publish(self):
        """Connect to running PubSub server, send and receive messages."""
        sio_client = SocketIO(self.server_addr, self.server_port, namespace=self)
        # sio_client.on('connect', self.sio_on_connect)
        # sio_client.on('disconnect', self.sio_on_disconnect)
        self._do_subscribe_publish(sio_client)

    def _do_subscribe_publish(self, sio):
        # expect server_hello on connect
        def on_server_hello(self, *args):
            print("GOT SERVER HELLO")
            self.got_server_hello = True
        sio.on('server_hello', on_server_hello)

        sio.wait(seconds=1)  # wait for connect
        sio.wait_for_callbacks(seconds=1)  # wait for connect
        sio.wait_for_callbacks(seconds=1)  # wait for connect
        # socketIO.emit('bbb', {'xxx': 'yyy'}, on_bbb_response)

        # self.assertTrue(self.sio_connected, "Did not get connect event")
        self.assertTrue(self.got_server_hello, "Did not get server hello event on connect")

        sio.wait(seconds=1)
