[![Build Status](https://travis-ci.org/revmischa/socketio_pg.svg?branch=master)](https://travis-ci.org/revmischa/socketio_pg)

SocketIO PostgreSQL PubSub Websocket Server
================

# What Is This?
This is a websocket server that uses PostgreSQL as its message transport system.

If you have an application that already uses postgres, you can easily send and receive asynchronous events via your existing database. Check out the [postgres documentation on LISTEN/NOTIFY](https://www.postgresql.org/docs/current/static/sql-notify.html) for more details.

# How Do I Use This?

## Server

### Configuration
First configure a database connection string in `DATABASE_URL`.
You can create a `local.cfg`:
```
# local.cfg
SQLALCHEMY_DATABASE_URI = 'postgresql:///mydatabase
DEBUG = True
```
Or set `DATABASE_URL` in your environment. If you use Heroku and have a database attached, this will be set already.

### Prerequisites
Note: python 3.6 or higher is required.
`pip install -r requirements.txt`

### Run
* Debug server mode: `DEBUG=1 python socketio_pg/server.py`
* In gunicorn (production): `gunicorn --worker-class eventlet -w 1 socketio_pg.server:app`
* If using Heroku, a Procfile is already set up for you.

## Client

On the client side, you simply connect a [socket.io client](https://socket.io/docs/client-api/) to begin sending and receiving events.
There's a simple demo HTML page at [socketio_pg/static/test.html](socketio_pg/static/test.html) that you can access from the dev server at [http://localhost:3030/static/test.html](http://localhost:3030/static/test.html).

# Why Use This?
If your application already uses PostgreSQL, you can start sending and receiving asynchronous events right away. It makes an excellent transport for messages (keep them small though, under 8000 bytes), and you can simply issue queries to do it. No additional infrastructure needed, besides this websocket server. If you aren't using PostgreSQL, [maybe you should be](https://spiegelmock.com/2014/10/19/mysql-vs-postgresql-and-why-you-care/).

One neat trick is to set up triggers that emit `NOTIFY` queries when rows on certain tables are inserted or updated. This allows messages to be delivered to clients notifying them of updates without any application code at all. Some demos and slides from a talk can be found [here](https://github.com/revmischa/pgnotify-demos).

# In Action
![socketio_pg in action](https://raw.githubusercontent.com/revmischa/socketio_pg/master/screenshot.png)

# How Is This Built?
This server uses the following technologies:
* Flask - python web microframework
* psycopg2 - postgresql driver
* [eventlet](http://eventlet.net/) - lightweight green threading library
* [greenlet](https://greenlet.readthedocs.io/en/latest/) - app threads in python
* socket.io - client and server layer on top of websockets to handle namespacing, reconnection, and basic session management
