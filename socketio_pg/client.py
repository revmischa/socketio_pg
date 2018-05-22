"""Send push events via postgresql NOTIFY."""
import logging
import re
import json
from typing import Dict
from psycopg2.extensions import quote_ident  # noqa

log = logging.getLogger(__name__)


class PayloadTooLargeError(Exception):
    pass


class Client:
    def __init__(self, connection):
        """Create PubSub interface for database connection."""
        self.connection = connection

    def sanitize_channel(self, channel: str) -> str:
        """Force channel to be plain alphanumeric strings."""
        return re.sub(r'\W+', '', channel)

    def publish(self, channel, event_name: str, params: Dict=None) -> None:
        """Publish message on channel."""
        channel = self.sanitize_channel(channel)

        # format:
        # { 'event_name': 'foo_event', params: { 'param1': 123 ... } }
        payload = dict(
            event_name=event_name,
            params=params,
        )

        json_payload = json.dumps(payload)
        if len(json_payload) > 8000:
            raise PayloadTooLargeError("Tried to publish payload with size greater than 8000 bytes")

        # publish
        conn_unwrapped = self.connection  # raw
        cur = conn_unwrapped.cursor()
        self._execute(cur, f'NOTIFY "{channel}", %s', json_payload)  # channel is sanitized above

    def _execute(self, cur, query, *bind_args):
        cur.execute(query, tuple(bind_args))
