"""Logger module for the control service. Outputs to stdout only."""

import logging
import os
import sys

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
