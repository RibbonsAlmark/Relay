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

# Image Compression Config
# Color Image
COLOR_IMG_MAX_WIDTH = int(os.getenv("COLOR_IMG_MAX_WIDTH", "1024"))
COLOR_IMG_QUALITY = int(os.getenv("COLOR_IMG_QUALITY", "50"))

# Depth Image
DEPTH_IMG_MAX_WIDTH = int(os.getenv("DEPTH_IMG_MAX_WIDTH", "640"))
DEPTH_IMG_COMPRESS = os.getenv("DEPTH_IMG_COMPRESS", "False").lower() == "true"

# Batch Sending Config
# Buffer size limit for batching (in bytes). Default: 1MB (1024 * 1024)
BATCH_BUFFER_SIZE_LIMIT = int(os.getenv("BATCH_BUFFER_SIZE_LIMIT", str(1024 * 1024)))
# Timeout for flushing batch buffer (in seconds). Default: 0.05 (50ms)
BATCH_BUFFER_TIMEOUT = float(os.getenv("BATCH_BUFFER_TIMEOUT", "0.05"))