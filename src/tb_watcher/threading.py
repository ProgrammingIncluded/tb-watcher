"""
Multithreading globa queue logic.

By: ProgrammingingIncluded
"""
import time
import threading

from queue import Queue

# includes main thread
THREADS = []
T_QUEUE = Queue()

BUSY_LOCK = threading.Lock()
BUSY_THREADS = 0
NUM_THREADS = 0

def get_job():
    global BUSY_LOCK
    global BUSY_THREADS

    task = None
    with BUSY_LOCK:
        try:
            task = T_QUEUE.get(block=False)
            BUSY_THREADS += 1
        except:
            pass
    return task

def worker_thread():
    global BUSY_LOCK
    global BUSY_THREADS

    while True:
        task = get_job()
        if task is None:
            time.sleep(0.2)
        else:
            task(True)
            with BUSY_LOCK:
                BUSY_THREADS -= 1

def spawn_threads(num_threads: int = 4):
    global NUM_THREADS
    NUM_THREADS = num_threads - 1
    assert num_threads >= 1, "There should be atleast a main thread."
    for _ in range(num_threads - 1):
        t = threading.Thread(target=worker_thread, args=())
        t.daemon = True
        t.start()

def threads_done():
    if NUM_THREADS == 0:
        return True

    with BUSY_LOCK:
        return T_QUEUE.qsize() == 0 and BUSY_THREADS == 0

def add_job(job):
    if NUM_THREADS == 0:
        job(False)
    else:
        T_QUEUE.put(job)
