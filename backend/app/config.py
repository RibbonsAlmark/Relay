# app/config.py (终极简单版)
import os

BACKEND_IP = os.getenv("BACKEND_IP", "192.168.18.104")
# BACKEND_IP = os.getenv("BACKEND_IP", "101.6.69.214")
BACKEND_PORT_STR = os.getenv("BACKEND_PORT", "9999")
BACKEND_PORT = int(BACKEND_PORT_STR)
BACKEND_HOST = f"{BACKEND_IP}:{BACKEND_PORT_STR}"

DEFAULT_DB = "db_prod"
DEFAULT_COL = "db_dev"

# Performance Tuning
# Number of worker threads multiplier relative to CPU cores (e.g., 2 means 2 * CPU_CORES)
WORKER_THREAD_MULTIPLIER = int(os.getenv("WORKER_THREAD_MULTIPLIER", "2"))

# Backpressure queue size multiplier relative to worker threads (e.g., 4 means 4 * WORKER_THREADS)
BACKPRESSURE_QUEUE_MULTIPLIER = int(os.getenv("BACKPRESSURE_QUEUE_MULTIPLIER", "4"))

# Number of concurrent sender threads for async data (images, etc.)
SENDER_THREAD_COUNT = int(os.getenv("SENDER_THREAD_COUNT", "4"))