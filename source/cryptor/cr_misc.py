'''
=========================================================================
* cr_misc.py                                                            *
=========================================================================
* This file contains general/misc. functions that are used by the       *
* Cryptor program.                                                      *
=========================================================================
'''
import os
import sys
import logging

from source.cryptor import cr_globals as cr_g


'''
=========================================================================
* setup_logger()                                                        *
=========================================================================
* This function sets up the program logger for errors and exceptions.   *
*                                                                       *
*   INPUT:                                                              *
*         None                                                          *
*                                                                       *
*   OUPUT:                                                              *
*         None                                                          *
=========================================================================
'''
def setup_logger() -> None:
    # Set log file path
    log_file = f"{os.getcwd()}{cr_g.LOGGER_PATH}{cr_g.LOGGER_FILE_NAME}{cr_g.LOGGER_EXT}"
    
    # Create a file handler to write to log file
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(filename)s | %(funcName)s | %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
    file_handler.setFormatter(file_formatter)

    # Create a stream handler to write to terminal
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
    stream_handler.setFormatter(stream_formatter)

    # Create root program logger
    logging.basicConfig(level=logging.INFO,                         # Set root logger level
                        handlers=[file_handler, stream_handler])    # Set root logger file and stream handlers

    return



'''
=========================================================================
* shutdown_logger()                                                     *
=========================================================================
* This function performs an orderly shutdown by flushing and closing    *
* all program logger handlers.                                          *
*                                                                       *
*   INPUT:                                                              *
*         None                                                          *
*                                                                       *
*   OUPUT:                                                              *
*         None                                                          *
=========================================================================
'''
def shutdown_logger() -> None:
    # Shutdown program logger
    logging.shutdown()

    return