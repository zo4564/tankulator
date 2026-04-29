
import logging

# --- LOGGER ---
logging.basicConfig(
    filename='aquarium_debug.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)

def log(msg):
    logging.info(msg)