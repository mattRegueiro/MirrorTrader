'''
=========================================================================
* mt_misc.py                                                            *
=========================================================================
* This file contains general/misc. functions that are used throughout   *
* the MirrorTrader execution.                                           *
=========================================================================
'''
import os
import sys
import time
import json
import socket
import logging
import argparse
import numpy as np
import pandas as pd
import datetime as dt
import pathlib as path
import pandas_market_calendars as market_calendar

from dateutil import tz
from colour import Color
from dateutil.parser import parse
from cryptography.fernet import Fernet
from holidays.countries import UnitedStates
from source.mirror_trader import mt_globals as mt_g


# '''
# =========================================================================
# * parse_args()                                                          *
# =========================================================================
# * This function sets up the program's command line parser and will      *
# * return parsed command line arguments.                                 *
# *                                                                       *
# *   INPUT:                                                              *
# *         None                                                          *
# *                                                                       *
# *   OUPUT:                                                              *
# *         args (argparse.Namespace)  - Parsed command line arguments.   *
# =========================================================================
# '''
# def parse_args():
#     # Create argument parser to parse command line arguments
#     #   MirrorTrader Arguments:
#     #       1.) -c / --config : The name of the encrypted config file that will contain login credential data for access to a 
#     #                           user's Webull, Discord, and SMS accounts.
#     #       2.) -d / --debug  : Optional argument that will have the program enter debug mode. This mode will display additional 
#     #                           output from normal runtime output.
#     #       3.) -x / --dev    : Optional argument that will have the program enter developer mode. This mode is used to develop 
#     #                           and maintain Discord trading channels.

#     parser = argparse.ArgumentParser(description="Option Trading Bot for $OWLS Discord Server")
#     parser.add_argument('-c' , '--config', type=str           , help="Encrypted config file containing credentials for Discord, Webull, and SMS login")
#     parser.add_argument('-d' , '--debug' , action='store_true', help="Enables debug mode to display additional outputs")
#     parser.add_argument('-x' , '--dev'   , action='store_true', help="Enables developer mode for Discord trading channels")

#     # Collect args from command line
#     args = parser.parse_args()

#     return args



'''
=========================================================================
* logger_setup()                                                        *
=========================================================================
* This function sets up the program logger for errors and exceptions.   *
*                                                                       *
*   INPUT:                                                              *
*         debug (bool) - Sets the logging output directory for debug    *
*                        mode.                                          *
*                                                                       *
*   OUPUT:                                                              *
*         None                                                          *
=========================================================================
'''
def setup_logger(debug=False):
    # Set log file path
    log_file = f"{mt_g.LOGGER_PATH}{mt_g.LOGGER_FILE_NAME}{mt_g.LOGGER_EXT}"
    if debug:
        log_file = f"{mt_g.LOGGER_DEBUG_PATH}{mt_g.LOGGER_FILE_NAME}{mt_g.LOGGER_EXT}"

    # If log file already exists
    if os.path.exists(log_file):

        # Create copy of original log file
        copy_file = f"{mt_g.LOGGER_PATH}{mt_g.LOGGER_FILE_COPY_NAME}{mt_g.LOGGER_EXT}"
        if debug:
            copy_file = f"{mt_g.LOGGER_DEBUG_PATH}{mt_g.LOGGER_FILE_COPY_NAME}{mt_g.LOGGER_EXT}"

        # If log file copy does not exist
        if not os.path.exists(copy_file):

            # Open original log file
            with open(log_file, "r") as orig:

                # Create and open log file copy
                with open(copy_file, "w") as copy:

                    # Copy contents of original log file to copy file
                    for line in orig:
                        copy.write(line)

            print(f"[{path.Path(__file__).stem}] Saved contents of {log_file} to {copy_file}!")     


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
* read_config()                                                         *
=========================================================================
* This function reads the configuration file containing Discord, Webull *
* and SMS login data.                                                   *
*                                                                       *
*   INPUT:                                                              *
*         config_file (str) - Config file containing Discord, Webull,   *
*                             and SMS login credentials.                *
*                                                                       *
*   OUPUT:                                                              *
*                  status (bool) - Config file found status.            *
*         data["Discord"] (dict) - Discord login data from config file. *
*          data["Webull"] (dict) - Webull login data from config file.  *
*             data["SMS"] (dict) - SMS login data from config file.     *
=========================================================================
'''
def read_config(config_file: str="default.config"):
    # If config file found
    if os.path.exists(config_file):
        try:
            file = open(config_file)                                # Open config file
            data = json.load(file)                                  # Load parameters from file

        # *** JSON Decode Error ***
        except json.decoder.JSONDecodeError:
            logging.error(f"++ [{path.Path(__file__).stem}] Config file format is invalid!")
            return (False, None, None, None, None)

        data['Discord'] = {k:v for k,v in data['Discord'].items()}  # Read Discord parameters from file
        data['Webull']  = {k:v for k,v in data['Webull'].items()}   # Read Webull parameters from file
        data['SMS']     = {k:v for k,v in data['SMS'].items()}      # Read SMS parameters from file
        data['Trading'] = {k:v for k,v in data['Trading'].items()}  # Read Trading parameters from file

        return (True, data["Discord"], data["Webull"], data["SMS"], data['Trading'])

    # Else config file not found
    else:
        logging.error(f"++ [{path.Path(__file__).stem}] Could not find config file: {config_file}")
        return (False, None, None, None, None)



'''
=========================================================================
* read_encrypt_config()                                                 *
=========================================================================
* This function reads an encrypted config file containing Discord,      *
* Webull, and SMS login data.                                           *
*                                                                       *
*   INPUT:                                                              *
*         encrypt_config_file (str) - Encrypted file containing Discord,*
*                                     Webull, and SMS login credentials.*
*                                                                       *
*   OUPUT:                                                              *
*                  status (bool) - Encrypted config file found status.  *
*         data["Discord"] (dict) - Discord login data from config file. *
*          data["Webull"] (dict) - Webull login data from config file.  *
*             data["SMS"] (dict) - SMS login data from config file.     *
=========================================================================
'''
def read_encrypt_config(encrypt_config_file: str="default.aes"):
    # If encrypted config file found
    if os.path.exists(encrypt_config_file):

        # If decryption key not found
        if not os.path.exists(mt_g.CRYPTOR_KEY_FILE_NAME):
            logging.warning(f"++ [{path.Path(__file__).stem}] Could not find decryption key file: {mt_g.CRYPTOR_KEY_FILE_NAME}")
            return (False, None, None, None, None)
        
        with open(mt_g.CRYPTOR_KEY_FILE_NAME, 'rb') as k, open(encrypt_config_file, 'rb') as f:
            key     = k.read()                              # Read decryption key from file
            data    = f.read()                              # Read encrypted data from config file

        try:
            fernet          = Fernet(key=key)               # Generate fernet instance using key
            decrypted_data  = fernet.decrypt(token=data)    # Decrypt config file data
            data            = json.loads(decrypted_data)    # Load parameters from file
        
        # *** JSON Decode Error ***
        except json.decoder.JSONDecodeError:
            logging.error(f"++ [{path.Path(__file__).stem}] Config file format is invalid!")
            return (False, None, None, None, None)
        
        data['Discord'] = {k:v for k,v in data['Discord'].items()}  # Read Discord parameters from file
        data['Webull']  = {k:v for k,v in data['Webull'].items()}   # Read Webull parameters from file
        data['SMS']     = {k:v for k,v in data['SMS'].items()}      # Read SMS parameters from file
        data['Trading'] = {k:v for k,v in data['Trading'].items()}  # Read Trading parameters from file

        return (True, data["Discord"], data["Webull"], data["SMS"], data['Trading'])
    
    # Else encrypted config file not found
    else:
        logging.error(f"++ [{path.Path(__file__).stem}] Could not find encrypted config file: {encrypt_config_file}")
        return (False, None, None, None, None)



'''
=========================================================================
* is_network_connected()                                                *
=========================================================================
* This function checks the network connection status by attempting to   *
* create a socket connection at '1.1.1.1' Domain Name System (DNS).     *
*                                                                       *
*   INPUT:                                                              *
*         None                                                          *
*                                                                       *
*   OUPUT:                                                              *
*          True (bool) - Network connection established.                *
*         False (bool) - Network connection NOT established.            *
=========================================================================
'''
def is_network_connected():
    try:
        # Attempt to create socket connection, if successful then network connection established
        socket.create_connection(("1.1.1.1", 53))
        return True

    # *** Network Not Connected ***
    except OSError:
        logging.error(f"++ [{path.Path(__file__).stem}] Network connection not established!")

    # *** Unknown Error ***
    except Exception:
        logging.error(f"++ [{path.Path(__file__).stem}] Unknown error occurred!", exc_info=True)
    
    return False 



'''
=========================================================================
* wait_for_network_connection()                                         *
=========================================================================
* This function will periodically check the internet connection status  *
* if network is not connected.                                          *
*                                                                       *
*   INPUT:                                                              *
*         None                                                          *
*                                                                       *
*   OUPUT:                                                              *
*         network_status (bool) - The network connection status.        *
=========================================================================
'''
def wait_for_network_connection():
    # Initialize network status
    network_status = False

    # Initialize timer to wait max <MAX_DISCORD_NETWORK_WAIT_TIME> minutes before exiting thread
    exit_timer = (dt.datetime.now() + dt.timedelta(minutes=mt_g.MAX_NETWORK_WAIT_TIME)).time()

    # Wait until internet network is established or timeout has been reached
    while (not network_status) and (dt.datetime.now().time() < exit_timer):

        # Wait (15) seconds before checking for network connection
        time.sleep(15)

        # Check internet connection status
        network_status = is_network_connected()

    # If network connection re-established
    if network_status:
        logging.info(f"[{path.Path(__file__).stem}] Internet connection established!")

    # Else network connection not established
    else:
        logging.error(f"[{path.Path(__file__).stem}] Failed to establish an internet connection!")
    
    return network_status 


'''
=========================================================================
* get_market_times()                                                    *
=========================================================================
* This function will determine and return the appropriate US stock      *
* market open and close times based off local timezone.                 *
*                                                                       *
*   INPUT:                                                              *
*       None                                                            *
*                                                                       *
*   OUPUT:                                                              *
*       market_open (dt.time())     - Market open time.                 *
*      market_close (dt.time())     - Market close time.                *
=========================================================================
'''
def get_market_times():
    # Get timezone name
    timezone = time.tzname[time.localtime().tm_isdst]

    if 'EASTERN' in timezone.upper():
        # Eastern Time (EST/EDT)
        market_open     = parse('09:30 AM').time()  # Market Open time          (09:30 AM)
        market_close    = parse('04:00 PM').time()  # Market Close time         (04:00 PM)

    elif 'CENTRAL' in timezone.upper():
        # Central Time (CST/CDT)
        market_open     = parse('08:30 AM').time()  # Market Open time          (08:30 AM)
        market_close    = parse('03:00 PM').time()  # Market Close time         (03:00 PM)

    elif 'MOUNTAIN' in timezone.upper():
        # Mountain Time (MST/MDT)
        market_open     = parse('07:30 AM').time()  # Market Open time          (07:30 AM)
        market_close    = parse('02:00 PM').time()  # Market Close time         (02:00 PM)

    else:
        # Pacific Time (PST/PDT)
        market_open     = parse('06:30 AM').time()  # Market Open time          (06:30 AM)
        market_close    = parse('01:00 PM').time()  # Market Close time         (01:00 PM)

    return (market_open, market_close)



'''
=========================================================================
* is_market_holiday()                                                   *
=========================================================================
* This function determines if today's date is a US stock market holiday.*
*                                                                       *
*   INPUT:                                                              *
*       None                                                            *
*                                                                       *
*   OUPUT:                                                              *
*       True (bool) - If today's date is a US stock market holiday.     *
*      False (bool) - If today's date is NOT a US stock market holiday  *
*                     or today's date is a early market closure holiday.*
=========================================================================
'''
def is_market_holiday():
    # Get list of US holidays
    US_holidays = UnitedStates(years=dt.datetime.now().date().year)

    # Get list of stock market holidays for the current year
    nyse = market_calendar.get_calendar("NYSE")
    holidays = list(filter(lambda x: pd.to_datetime(x).year == dt.date.today().year, nyse.holidays().holidays))

    # If today's date is a stock market closure holiday
    if np.datetime64('today') in holidays:

        # Convert numpy datetime to pandas datetime object
        closure_date = pd.to_datetime(np.datetime64('today')).date()
        
        try:
            # Closure date is a US federal holiday
            logging.error(f"++ [{path.Path(__file__).stem}] US Stock Market closed today because of {US_holidays[closure_date]}!")
        
        # *** Key Error ***
        except KeyError:
            # Closure date is not a US federal holiday
            logging.error(f"++ [{path.Path(__file__).stem}] US Stock Market closed today because of non-federal holiday!")

        return True

    # Else today's date is not a stock market closure holiday
    else:

        # Determine if today's date has an early stock market closure time
        date = pd.to_datetime(np.datetime64('today')).date()
        early_close_times = nyse.early_closes(schedule=nyse.schedule(start_date=date.strftime(mt_g.DATE_FORMAT_YYYY_MM_DD), \
                                                                     end_date=date.strftime(mt_g.DATE_FORMAT_YYYY_MM_DD)))

        # If early open/close times available for today's date
        if not early_close_times.empty:

            # Convert early open/close times to datetime objects
            early_open_time = pd.to_datetime(early_close_times['market_open'].values[0])
            early_close_time = pd.to_datetime(early_close_times['market_close'].values[0])

            # Convert early open/close times from UTC to local timezone
            early_open_time = early_open_time.replace(tzinfo=dt.timezone.utc).astimezone(tz=tz.tzlocal()).time()
            early_close_time = early_close_time.replace(tzinfo=dt.timezone.utc).astimezone(tz=tz.tzlocal()).time()

            # Update market open and close times
            mt_g.MARKET_OPEN_TIME = early_open_time
            mt_g.MARKET_CLOSE_TIME = early_close_time

            # If the next day is a holiday
            if (date + dt.timedelta(days=1)) in US_holidays:
                
                # Display holiday information
                early_closure_holiday = US_holidays[(date + dt.timedelta(days=1))]
                logging.warning(f"++ [{path.Path(__file__).stem}] US Stock Market closing early today because of day before {early_closure_holiday}!")
        
            # Else if the previous day was a holiday
            elif (date - dt.timedelta(days=1)) in US_holidays:
                
                # Display holiday information
                early_closure_holiday = US_holidays[(date - dt.timedelta(days=1))]
                logging.warning(f"++ [{path.Path(__file__).stem}] US Stock Market closing early today because of day after {early_closure_holiday}!")
        
    return False



'''
=========================================================================
* is_weekend()                                                          *
=========================================================================
* This function determines if today's date is a weekend.                *
*                                                                       *
*   INPUT:                                                              *
*       None                                                            *
*                                                                       *
*   OUPUT:                                                              *
*       True (bool) - If today's date is a weekend (Sat/Sun).           *
*      False (bool) - If today's date is NOT a weekend (Mon-Fri).       *
=========================================================================
'''
def is_weekend():
    # Get the day of the week 
    # (Mon = 0 / Tue = 1 / Wed = 2 / Thur = 3 / Fri = 4 / Sat = 5 / Sun = 6)
    day_of_the_week = dt.datetime.today().weekday()

    # If weekday (Mon - Fri)
    if day_of_the_week < 5:
        return False

    # Else weekend (Sat - Sun)
    else:
        logging.error(f"++ [{path.Path(__file__).stem}] US Stock Market closed on weekends!")
        return True



'''
=========================================================================
* wait_till_market_open()                                               *
=========================================================================
* This function will loop and wait until the current time is equal to   *
* the stock market open time (6:30 AM PDT).                             *
*                                                                       *
*   INPUT:                                                              *
*         None                                                          *
*                                                                       *
*   OUPUT:                                                              *
*         None                                                          *
=========================================================================
'''
def wait_till_market_open():
    try:
        # Wait until the market opens before looking for trades
        wait_time = (dt.datetime.combine(dt.date.today(), mt_g.MARKET_OPEN_TIME) - dt.datetime.now()).total_seconds()
        time.sleep(wait_time)

    # *** Keyboard Exit ***
    except KeyboardInterrupt:
        
        # Set program shutdown event
        mt_g.PROGRAM_SHUTDOWN.set()

    # *** Unknown Error ***
    except Exception:
        logging.error(f"[{path.Path(__file__).stem}] Unknown error occurred!", exc_info=True)

    return 



'''
=========================================================================
* get_nearest_known_color()                                             *
=========================================================================
* This function will take a hex-valued color and determine the nearest  *
* primary color.                                                        * 
*                                                                       *
*   INPUT:                                                              *
*         hex_color (str) - Color as hex string.                        *
*                                                                       *
*   OUPUT:                                                              *
*       definition (str)    - The meaning of the response code.         *
=========================================================================
'''
def get_nearest_known_color(hex_color=""):
    # Get color from color hex value
    color_to_match = Color(hex_color)

    # Initialize color distance and match
    best_distance = sys.float_info.max
    best_match = Color()

    # Loop through each base color to find approximate color match
    for base_color in mt_g.BASE_COLORS:
        
        # Calculate difference from base color
        delta_r = abs(base_color.get_red() - color_to_match.get_red())
        delta_g = abs(base_color.get_green() - color_to_match.get_green())
        delta_b = abs(base_color.get_blue() - color_to_match.get_blue())
        total_distance = delta_r + delta_g + delta_b

        # If color match is closer than last color match, update best match
        if total_distance < best_distance:
            best_match = base_color
            best_distance = total_distance

    return best_match



'''
=========================================================================
* http_response_codes()                                                 *
=========================================================================
* This function will take a HTTP response code and return the meaning / *
* definition of the HTTP code (used for debugging purposes).            *
*                                                                       *
*   INPUT:                                                              *
*             code (int)    - The HTTP response code.                   *
*                                                                       *
*   OUPUT:                                                              *
*       definition (str)    - The meaning of the response code.         *
=========================================================================
'''
def http_response_codes(code=None):
    if code is None:
        return None

    if code == 200:
        definition = "Request completed successfully."
    elif code == 201:
        definition = "Entity was created successfully."
    elif code == 204:
        definition = "Request completed successfully, but no content returned."
    elif code == 304:
        definition = "Entity was not modified (no action taken)."
    elif code == 400:
        definition = "Request was improperly formatted."
    elif code == 401:
        definition = "'Authorization' header missing or invalid."
    elif code == 403:
        definition = "'Authorization' token did not have permission to the resource."
    elif code == 404:
        definition = "Resource at the location specified does not exist."
    elif code == 405:
        definition = "HTTP method used is not valid for the location specified."
    elif code == 429:
        definition = "Rate limit has been applied."
    elif code == 500:
        definition = "Internal Server Error."
    elif code == 502:
        definition = "No gateway available to process request. Wait a bit and retry."
    elif code > 502:
        definition = "Server had an error processing the request (rare issue)."
    else:
        definition = "Unknown HTTP response code!"

    return definition



'''
=========================================================================
* display_banner()                                                      *
=========================================================================
* This function displays the Mirror Trader program title.               *
*                                                                       *
*   INPUT:                                                              *
*         None                                                          *
*                                                                       *
*   OUPUT:                                                              *
*         None                                                          *
=========================================================================
'''
def display_banner():
    
    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print(" /$$      /$$ /$$                                               /$$$$$$$$                       /$$                    ")
    print("| $$$    /$$$|__/                                              |__  $$__/                      | $$                    ")
    print("| $$$$  /$$$$ /$$  /$$$$$$   /$$$$$$   /$$$$$$   /$$$$$$          | $$  /$$$$$$  /$$$$$$   /$$$$$$$  /$$$$$$   /$$$$$$ ")
    print("| $$ $$/$$ $$| $$ /$$__  $$ /$$__  $$ /$$__  $$ /$$__  $$         | $$ /$$__  $$|____  $$ /$$__  $$ /$$__  $$ /$$__  $$")
    print("| $$  $$$| $$| $$| $$  \__/| $$  \__/| $$  \ $$| $$  \__/         | $$| $$  \__/ /$$$$$$$| $$  | $$| $$$$$$$$| $$  \__/")
    print("| $$\  $ | $$| $$| $$      | $$      | $$  | $$| $$               | $$| $$      /$$__  $$| $$  | $$| $$_____/| $$      ")
    print("| $$ \/  | $$| $$| $$      | $$      |  $$$$$$/| $$               | $$| $$     |  $$$$$$$|  $$$$$$$|  $$$$$$$| $$      ")
    print("|__/     |__/|__/|__/      |__/       \______/ |__/               |__/|__/      \_______/ \_______/ \_______/|__/      ")
    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    
    return
