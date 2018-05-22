from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='socketio_pg',
    version='0.7',
    description='Websocket server using PostgreSQL as a message transport. Uses SocketIO, Greenlet, Flask.',
    url='http://github.com/revmischa/socketio_pg',
    author='Mischa Spiegelmock',
    author_email='revmischa@cpan.org',
    license='ABRMS',
    packages=['socketio_pg'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='websocket pubsub socketio socket.io greenlet eventlet postgresql postgres psycopg2 server',
    setup_requires=['setuptools>=38.6.0'],
    install_requires=requirements,
)
