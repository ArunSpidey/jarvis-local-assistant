# jarvis_logger.py

import os
import logging

os.makedirs("logs", exist_ok=True)

log_file = "logs/jarvis.log"

logging.basicConfig(
    filename=log_file,
    filemode="a",
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Define and export the logger
logger = logging.getLogger("jarvis")
