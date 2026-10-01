"""Logger module for the control service. Outputs to stdout only."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from config import updater_log_file

# The poll runs every minute forever, so anything logged on the quiet path is written
# 1440 times a day. Routine progress belongs at DEBUG; INFO is for what actually
# happened. Set LOG_LEVEL=DEBUG to get the detail back while diagnosing.
level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").strip().upper(), logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(level)

formatter = logging.Formatter("%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s")

# Stream handler (stdout only)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(level)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# The updater's own log, so "what has this node been doing about updates" can be read
# without picking it out of a minute-by-minute monitoring log. Served at
# /service/updater/logs, which until now had a route and no file behind it.
#
# A copy rather than a move: these lines still go to stdout and so into control's log,
# which stays the complete narrative. Removing them from there would make control's log
# harder to follow for the sake of a view that can just as easily be a filter.
#
# Rotated here rather than by run-control.sh, which only knows about control's log. Same
# ceiling, 10MB and three generations.
updater_handler = RotatingFileHandler(
    updater_log_file,
    maxBytes=int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024)),
    backupCount=int(os.getenv("LOG_KEEP", 3)),
)
updater_handler.setLevel(level)
updater_handler.setFormatter(formatter)
# Every module shares this one logger, so the record's own filename is what separates the
# updater's lines from the rest.
updater_handler.addFilter(lambda record: record.filename == "updater.py")
logger.addHandler(updater_handler)
