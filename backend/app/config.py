# app/config.py (终极简单版)
import os

BACKEND_IP = os.getenv("BACKEND_IP", "192.168.18.104")
# BACKEND_IP = os.getenv("BACKEND_IP", "101.6.69.214")
BACKEND_PORT_STR = os.getenv("BACKEND_PORT", "9999")
BACKEND_PORT = int(BACKEND_PORT_STR)
BACKEND_HOST = f"{BACKEND_IP}:{BACKEND_PORT_STR}"

DEFAULT_DB = "db_prod"
DEFAULT_COL = "db_dev"