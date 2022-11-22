"""
General program logger settup.
By: ProgrammingIncluded
"""
import logging

logger = logging.getLogger("tb_watcher")
s_handler = logging.StreamHandler()

# Default severity level
s_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("[%(name)s][%(levelname)s] %(message)s")
s_handler.setFormatter(formatter)
