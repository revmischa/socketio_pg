web: gunicorn --worker-class eventlet -w 1 socketio_pg.server:app
debug: FLASK_DEBUG=1 python3 socketio_pg/server.py
debug-gunicorn: FLASK_DEBUG=1 gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:3030 --reload socketio_pg.server:app
