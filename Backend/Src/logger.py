import os
import sys
import logging
import logging.handlers
from Src.path import LOG_FILE_PATH

def setup_loggers():
    """Initializes and returns two loggers: one for the file, one for the console."""
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # 1. File Logger (Detailed format with timestamps)
    f_logger = logging.getLogger("FileLogger")
    f_logger.setLevel(logging.INFO)
    f_logger.propagate = False
    if f_logger.hasHandlers():
        f_logger.handlers.clear()
        
    f_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    f_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=1024*1024, backupCount=1, mode='a'
    )
    f_handler.setFormatter(f_formatter)
    f_logger.addHandler(f_handler)

    # 2. Console Logger (Clean format to replace 'print')
    c_logger = logging.getLogger("ConsoleLogger")
    c_logger.setLevel(logging.INFO)
    c_logger.propagate = False
    if c_logger.hasHandlers():
        c_logger.handlers.clear()
        
    c_formatter = logging.Formatter('%(message)s')
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setFormatter(c_formatter)
    c_logger.addHandler(c_handler)
    
    return f_logger, c_logger