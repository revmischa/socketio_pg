"""Publish-subscribe mechanism for postgresql."""

import flask
import psycopg2.extensions
import re
import logging
import eventlet
import json
from select import select
from eventlet.hubs import trampoline
from eventlet.semaphore import Semaphore
from typing import List, Dict
from psycopg2.extensions import quote_ident
from contextlib import contextmanager

log = logging.getLogger(__name__)


EventName = str
ListenerQueue = eventlet.Queue
ListenerList = List[ListenerQueue]
EventListeners = Dict[EventName, ListenerList]


class PayloadTooLargeError(Exception):
    pass


class NoEventsReadyException(Exception):
    pass


class PubSub():
    def __init__(self, app: flask.Flask, dsn: str) -> None:
        """Initialize with flask application."""
        self.app = app
        self.dsn = dsn
        self.listeners: EventListeners = dict()
        self.conn = self._new_connection()
        self.debug = True  # set for more verbosity
        self.listen_greenthread = None
        self.conn_sem = Semaphore()
        self.read_timeout = .3
        self.cursor = self.conn.cursor()

        self.listen()

    def disconnect(self):
        """Disconnect and stop listening."""
        if self.listen_greenthread:
            self.listen_greenthread.kill()
            self.listen_greenthread = None
        with self.conn_sem:
            self.conn.close()

    @contextmanager
    def disable_listener(self):
        """Run block of code with the connection trampoline disabled.

        This is necessary when performing operations on the connection (i.e. issueing queries)
        because eventlet doesn't like it when two threads try to select()/poll() the same fd at the same time.
        """
        was_listening: bool = self.listen_greenthread is not None
        if was_listening:
            self.listen_greenthread.kill()
            self.listen_greenthread = None

        with self.conn_sem:
            yield
            self._check_for_notifies()

        if was_listening:
            self.listen(wait=2)

    def sanitize_event_name(self, event_name: EventName) -> EventName:
        """Force event names to be plain alphanumeric strings."""
        return re.sub(r'\W+', '', event_name)

    def wait(self, conn=None, timeout=None):
        """Wait for an operation to complete."""
        # http://initd.org/psycopg/docs/advanced.html#asynchronous-support
        if not conn:
            conn = self.conn
        while 1:
            state = conn.poll()
            if state == psycopg2.extensions.POLL_OK:
                break
            elif state == psycopg2.extensions.POLL_WRITE:
                select([], [conn.fileno()], [], timeout)
            elif state == psycopg2.extensions.POLL_READ:
                select([conn.fileno()], [], [], timeout)
            else:
                raise psycopg2.OperationalError("poll() returned %s" % state)

    def _new_connection(self):
        """Connect to DB."""
        conn = psycopg2.connect(self.dsn, async=True)
        # wait until connected
        self.wait(conn)
        return conn

    def unsubscribe(self, subscription):
        """Cancel a subscription."""
        queue = subscription['queue']
        event_name = subscription['event_name']
        if event_name not in self.listeners:
            return
        # remove listener
        listeners = self.listeners[event_name]
        self.listeners[event_name] = list(filter(lambda l: l is not queue, listeners))
        # unlisten if no more listeners left
        if len(self.listeners[event_name]) == 0:
            self._unsubscribe(event_name)
            del self.listeners[event_name]

    def subscribe(self, event_name: EventName, queue: ListenerQueue):
        """Listen for event_name notifications and send a message on queue when received."""
        event_name = self.sanitize_event_name(event_name)

        # get current list of listeners on this channel
        if event_name not in self.listeners:
            self.listeners[event_name] = list()
            self._subscribe(event_name)
        listeners: ListenerList = self.listeners[event_name]
        listeners.append(queue)
        subscription = {'queue': queue, 'event_name': event_name}
        return subscription

    def _subscribe(self, event_name: EventName):
        """Stop waiting for events, listen for event_name, begin listening to events again."""
        # cur = self.conn.cursor()
        cur = self.cursor

        # tell our pg connection to listen to events from this channel
        with self.disable_listener():
            cur.execute(f"LISTEN {quote_ident(event_name, cur)}")
            self.wait()

        self._debug(f"Listening on {event_name}")

    def _unsubscribe(self, event_name: EventName):
        """Unlisten on event_name."""
        cur = self.cursor

        # tell our pg connection to stop listening to events from this channel
        with self.disable_listener():
            cur.execute(f"UNLISTEN {quote_ident(event_name, cur)}")
            self.wait()

        self._debug(f"Canceled listen on {event_name}")

    def _debug(self, msg: str):
        if not self.debug:
            return
        log.warning(msg)

    def handle_event(self, notify):
        """Got notification from postgres."""
        self._debug(f"Got notify: {notify}")
        event_name: EventName = notify.channel
        if event_name not in self.listeners:
            self._debug(f"No listeners found for {event_name}")
            return

        # parse payload as JSON (it should be a JSON string if it came from us)
        payload = notify.payload
        if payload:
            try:
                payload = json.loads(payload)
            except Exception as ex:
                log.error(f"Failed to parse payload as JSON: {payload}.\nError: {ex}")

        listeners = self.listeners[event_name]
        self._debug(f"{len(listeners)} listeners found for {event_name}")
        for queue in listeners:
            queue.put_nowait({
                'channel': event_name,
                'payload': payload,
            })

    def publish(self, event_name, payload=None):
        """Publish message on channel."""
        event_name: EventName = self.sanitize_event_name(event_name)
        if not payload:
            payload = {}

        json_payload = json.dumps(payload)
        if len(json_payload) > 8000:
            raise PayloadTooLargeError("Tried to publish payload with size greater than 8000 bytes")

        cur = self.cursor

        q = f"NOTIFY {quote_ident(event_name, cur)}, %s"
        self._debug(f"Publishing {event_name}: {json_payload}")
        with self.disable_listener():
            cur.execute(q, (json_payload,))
            self.wait()

    def listen(self, wait=None):
        """Select on postgres connection for async notify events."""
        self.listen_greenthread = eventlet.spawn(self._listen, wait=wait)

    def _listen(self, wait=None):
        if wait:
            eventlet.greenthread.sleep(1)
        try:
            while True:
                with self.conn_sem:
                    try:
                        # select() until conn is readable (notification is available)
                        trampoline(self.conn, read=True, timeout=self.read_timeout, timeout_exc=NoEventsReadyException)
                    except NoEventsReadyException:
                        # timed out waiting for read
                        continue

                    self._check_for_notifies()
        except eventlet.greenlet.GreenletExit:
            return

    def check_for_notifies(self):
        """Check if we've received any pg async notifications and dispatch if we have."""
        with self.conn_sem:
            self._check_for_notifies()

    def _check_for_notifies(self):
        self.conn.poll()  # get available notifications
        while self.conn.notifies:
            n = self.conn.notifies.pop()
            self.handle_event(n)
