"""Test websocket/pubsub.

Run with: pytest socketio_pg/tests/test_pubsub.py
"""

from unittest import TestCase
from socketio_pg.websocket import SocketServer
from socketio_pg.app import create_app
import eventlet


class PubSubTestCase(TestCase):
    def setUp(self):
        """Initialize pubsub websocket server."""
        super().setUp()
        app = create_app()
        dsn = app.config['SQLALCHEMY_DATABASE_URI']
        self.ws = SocketServer(app=app, dsn=dsn, test=True)
        self.pubsub = self.ws.pubsub
        self.app = app

    def tearDown(self):
        """Shut down pubsub websocket server."""
        self.ws.shutdown()
        super().tearDown()

    def test_ws_client_server(self):
        """Connect to websocket server and test bidirectional communication."""
        self._do_pubsub_test()

    def _do_pubsub_test(self, channel_name='test'):
        client = self.ws.socketio.test_client(self.app)

        received = client.get_received()

        self.assertEqual(len(received), 1, "Didn't get one message on connect")
        self.assertEqual(received[0]['name'], 'server_hello', "Didn't get server_hello on connect")
        self.assertTrue(received[0]['args'][0]['client'], "Didn't get client on connect")

        # subscribe to test1
        client.emit('subscribe', {'channel': channel_name})
        received = client.get_received()
        args = received[0]['args'][0]
        self.assertEqual(len(received), 1, "Didn't get one message on subscribe")
        self.assertEqual(received[0]['name'], 'subscribed', "Didn't get subscribed on subscribe")
        self.assertEqual(args['channel'], channel_name, "Didn't get subscribed channel on subscribe")

        def send_and_receive():
            client.emit('test_pub', {
                'channel': channel_name,
                'payload': {'arg1': 123, 'arg2': True},
            })
            received = client.get_received()
            args = received[0]['args'][0]
            self.assertEqual(len(received), 1, "Didn't get one message on publish")
            self.assertEqual(received[0]['name'], 'published', "Didn't get published on subscribe")
            self.assertEqual(args['channel'], channel_name, "Didn't get publish channel on publish")

            self.ws.socketio.sleep(.2)  # let other threads do stuff

            # now should get notification
            received = client.get_received()
            self.assertEqual(len(received), 1, f"Didn't receive published message on {channel_name}")
            self.assertEqual(received[0]['name'], 'event', "Didn't get event message")
            args = received[0]['args'][0]  # our message that we received (after publishing)
            self.assertEqual(args['channel'], channel_name, "Didn't get channel on event")
            self.assertIs(args['payload']['arg1'], 123, "Didn't get payload arg")
            self.assertIs(args['payload']['arg2'], True, "Didn't get payload arg")

        send_and_receive()
        send_and_receive()

        client.disconnect()
        return True

    def test_load(self):
        """Connect a bunch of times, send a bunch of messages."""
        client_count = 50

        class TestClient():
            def __init__(self, num):
                self.num = num

        def run_test(client):
            return self._do_pubsub_test(channel_name=f"test_{client.num}")

        # make test clients
        clients = [TestClient(i) for i in range(client_count)]

        # run tests
        pool = eventlet.GreenPool()
        for result in pool.imap(run_test, clients):
            self.assertTrue(result, "Failed to complete load subtest")

        pool.waitall()
