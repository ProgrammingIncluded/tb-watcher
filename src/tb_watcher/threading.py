"""
Multithreading globa queue logic.

By: ProgrammingingIncluded
"""

import threading

from queue import Queue

# includes main thread
THREADS = []
T_QUEUE = Queue()

BUSY_LOCK = threading.RLock()
BUSY_THREADS = 0

def worker_thread():
    global BUSY_LOCK
    global BUSY_THREADS

    while True:
        # Blocking
        task = T_QUEUE.get()

        with BUSY_LOCK:
            BUSY_THREADS += 1

        task()

        with BUSY_LOCK:
            BUSY_THREADS -= 1

def spawn_threads(num_threads: int = 4):
    assert num_threads >= 1, "There should be atleast a main thread."
    for _ in range(num_threads - 1):
        t = threading.Thread(target=worker_thread, args=())
        t.daemon = True
        t.start()
