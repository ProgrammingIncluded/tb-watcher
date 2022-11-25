"""
Multithreading globa queue logic.

By: ProgrammingingIncluded
"""

import time
import threading

from queue import Queue

# includes main thread
MAX_THREADS = 2
THREADS = []
T_QUEUE = Queue()

def worker_thread():
    while True:
        time.sleep(0.5)
        task = T_QUEUE.get()
        task()

def spawn_threads():
    for _ in range(MAX_THREADS - 1):
        t = threading.Thread(target=worker_thread, args=())
        t.daemon = True
        t.start()
