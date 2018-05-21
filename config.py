"""Default configuration.

Put your local configuration in local.cfg.
"""

import os

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
SQLALCHEMY_TRACK_MODIFICATIONS = False
