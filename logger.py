# ==================================================================================
# Project: GoogleLineSys
# Author: Breno Alves
# Email: breno.alves@lumentum.com
# ==================================================================================

import logging
from logging import Logger
import logol
import os
from logol import get_logger as _get_logger
from datetime import datetime

logger_name = "Log-Switch"

def get_logger() -> Logger:
    if logger_name not in logol.__loggers:
        parent_path = os.path.dirname(os.path.dirname(__file__))
        log_path = os.path.join(parent_path, "logs")
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = os.path.join(log_path, f"Switch_Log_{date_time}.log")
        logger = _get_logger(logger_name, log_filename, force=True)
        # Set Console Handler to Debug Level
        for hndlr in logger.handlers:
            if isinstance(hndlr, logging.StreamHandler):
                hndlr.setLevel(logging.DEBUG)
        return logger
    
    return _get_logger(logger_name)
