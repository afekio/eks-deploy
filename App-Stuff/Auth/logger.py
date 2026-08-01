import logging
import os

def setup_logger():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Initialize logger
    auth_logger = logging.getLogger('AuthServiceLogger')
    auth_logger.setLevel(logging.DEBUG)

    # File Handler - writes logs to a file inside the instance
    file_handler = logging.FileHandler('logs/auth_service.log')
    file_handler.setLevel(logging.INFO)

    # Formatter - clean and readable format
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)

    # Add handler to logger (prevent duplicate handlers)
    if not auth_logger.handlers:
        auth_logger.addHandler(file_handler)

    return auth_logger