"""
General program logger settup.
By: ProgrammingIncluded
"""
import logging

LOG_FORMAT = "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"
logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger("tb_watcher")
logger.setLevel(logging.INFO)

# Pass-thru
logger.INFO = logging.INFO
logger.DEBUG = logging.DEBUG
