'''
=========================================================================
* mt_globals.py                                                         *
=========================================================================
* This file contains all global variables used by MirrorTrader.         *
=========================================================================
'''
import re
import ssl
import queue as q
import threading as t
import datetime as dt

from colour import Color
from source.mirror_trader import mt_misc as misc



###################################################################
#   G L O B A L   P A T H S   A N D   V A R I A B L E S           #
###################################################################
LOGGER_PATH                                 = f"logs/mirror_trader/"
LOGGER_DEBUG_PATH                           = f"logs/mirror_trader/debug/"
LOGGER_FILE_NAME                            = f"mirror_trader_{dt.datetime.today().date()}"
LOGGER_FILE_COPY_NAME                       = f"mirror_trader_{dt.datetime.today().date()}_COPY"
LOGGER_EXT                                  = ".log"

ACTIVE_THREADS                              = []                            # List of active program threads
PROGRAM_QUEUE                               = q.Queue()                     # Program queue to collect messages across all threads
WORKING_ORDERS_QUEUE                        = q.Queue()                     # Working orders queue to process active orders
TRADE_ALERTS_QUEUE                          = q.Queue()                     # Trade alerts queue to remove trades from trade tracker lists

MARKET_OPEN                                 = t.Event()                     # Event raised when US stock market is open
PROGRAM_SHUTDOWN                            = t.Event()                     # Event raised when shutdown message received by SMS bot
DEVELOPER_MODE                              = t.Event()                     # Event raised when developer mode has been enabled
NO_NETWORK_CONNECTION                       = t.Event()                     # Event raised when all threads are not active and no internet connection is established

MAX_NETWORK_WAIT_TIME                       = 10                            # Max amount of time to wait for network connection (minutes)
MAX_PERIODIC_CHECK_WAIT_TIME                = 30                            # Max amount of time to wait until threads can be checked for active status (seconds)


# #####################################################################
# #   E N C R Y P T I O N / D E C R Y P T I O N   V A R I A B L E S   #
# #####################################################################
CRYPTOR_KEY_FILE_NAME                       = "cryptor_key.key"             # Encryption/Decryption key file name (place this in system environment variables ??)
ENCRYPT_EXT                                 = ".aes"                        # Encrypted File Extension
DECRYPT_EXT                                 = ".config"                     # Decrypted File Extension



###################################################################
#   D A T E T I M E   T I M E   A N D   D A T E   F O R M A T S   #
###################################################################
TIME_FORMAT_12HR                            = "%I:%M %p"                    # 12-Hour time format
DATE_FORMAT_YYYY_MM_DD                      = "%Y-%m-%d"                    # Datetime format yyyy-mm-dd
DATE_FORMAT_DD_MONTH_YYYY                   = "%d-%b-%Y"                    # Datetime format dd_month_yyyy



# #################################################################
# #   S T O C K   M A R K E T   G L O B A L   V A R I A B L E S   #
# #################################################################
MARKET_OPEN_TIME, MARKET_CLOSE_TIME         = misc.get_market_times()       # Get US Stock Market Open/Close times


#####################################################
#   W E B U L L   G L O B A L   V A R I A B L E S   #
#####################################################
MAX_WEBULL_LOGIN_ATTEMPTS                   = 4                             # Max number of webull login attempts available
MFA_PIN_TIMEOUT                             = 30 * 60                       # MFA verification pin timeout in seconds (30 minutes)
WEBULL_TIMEOUT                              = 2 * 60                        # Webull timeout in seconds (2 minutes)

MAX_WAIT_TIMEOUT                            = 10                            # Max time to wait before timeout (seconds)
MODIFY_LIMIT_ORDER_TIMEOUT                  = 10                            # Limit order modify timeout in seconds
MAX_FAILED_ORDER_MODIFY_ATTEMPTS            = 3                             # Max number of failed modified order attempts
MAX_SPREAD_DIFF                             = 10                            # Max price difference between the bid and ask price

PRICE_INCREMENT                             = 0.05                          # Price increment when order price is between 0.0 and 3.0
STOP_LOSS_ADJUSTMENT_PERCENT                = 0.1                           # Stop loss adjustment percent when modifying stop loss orders

PROFIT_REPORT_DIR                           = "reports/"                    # Path to profit/loss report for each trading day 
MAX_TRADES_TO_REPORT                        = 300                           # Maximum number of trades to report in a single trading day


#######################################################
#   D I S C O R D   G L O B A L   V A R I A B L E S   #
#######################################################
TRACKER_DIR                                 = "trackers/"                   # Path to Mirror Trader tracker files
TRACKER_DEBUG_DIR                           = "trackers/debug/"             # Path to Mirror Trader debug tracker files
TRACKER_FILE_TYPE                           = ".tracker"                    # Trade tracker file type

DISCORD_REMOTE_DISCONNECT_WAIT_TIME         = 3                             # Wait time before attempting to re-collect channel messages
DISCORD_CHANNEL_MESSAGE_LIMIT               = 50                            # Max number of channel messages that are received from a single API request

MAX_DISCORD_LOGIN_ATTEMPTS                  = 4                             # Max number of discord login attempts available
MAX_DISCORD_SEARCH_ATTEMPTS                 = 3                             # Max number of attempts available to search for a specific Discord server and channel

SELL_ALL_PERCENT                            = 1.0                           # Sell all / Stopped out sell percent
SELL_MOST_PERCENT                           = 0.75                          # Sell 75%
SELL_HALF_PERCENT                           = 0.5                           # Sell 50%
SELL_SOME_PERCENT                           = 0.25                          # Sell 25%
SELL_ANOTHER_PERCENT                        = 0.01                          # Sell single option contract

EMOJI_FILTER                                = re.compile("["                # Filter to find emojis
                                                        u"\U0001F600-\U0001F64F"  # emoticons
                                                        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                                        u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                                        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                                                        u"\U00002500-\U00002BEF"  # chinese char
                                                        u"\U00002702-\U000027B0"
                                                        u"\U00002702-\U000027B0"
                                                        u"\U000024C2-\U0001F251"
                                                        u"\U0001f926-\U0001f937"
                                                        u"\U00010000-\U0010ffff"
                                                        u"\u2640-\u2642"
                                                        u"\u2600-\u2B55"
                                                        u"\u200d"
                                                        u"\u23cf"
                                                        u"\u23e9"
                                                        u"\u231a"
                                                        u"\ufe0f"  # dingbats
                                                        u"\u3030"
                                                        "]+", flags=re.UNICODE)

NUMERIC_STRINGS                             = ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]
STRING_NUMERICS                             = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
GUILD_TAG                                   = '<@&718643370301325404>'

BASE_COLORS                                 = [Color("red"), Color("yellow"), Color("green"), Color("cyan"), 
                                               Color("blue"), Color("magenta"), Color("white"), Color("black")]



###############################################################################
#   E M A I L   S M S   M E S S A G I N G   G L O B A L   V A R I A B L E S   #
###############################################################################
SMS_IMAP_HOST                               = "imap.gmail.com"              # IMAP host address for Gmail
SMS_IMAP_PORT                               = 993                           # IMAP port
SMS_SMTP_HOST                               = "smtp.gmail.com"              # SMTP host address for Gmail
SMS_SMTP_PORT                               = 465                           # SMTP port
SMS_SSL                                     = ssl.create_default_context()  # Use Secure Socket Layer (SSL)

PERIODIC_NOOP_MINUTES                       = 5                             # Number of minutes to wait until a NOOP command can be sent
MAX_PERIODIC_NOOP_WAIT_TIME                 = PERIODIC_NOOP_MINUTES * 60    # Max NOOP wait time for SMSBot (seconds)
IDLE_WAIT_MINUTES                           = 5                             # Number of minutes to sit in Idle
MAX_SMS_IDLE_WAIT_TIME                      = IDLE_WAIT_MINUTES * 60        # Max Idle Wait Time for SMSBot (seconds)
MAX_SMS_LOGIN_ATTEMPTS                      = 4                             # Max number of SMS login attempts available
MAX_SMS_SEND_ATTEMPTS                       = 5                             # Max number of attempts made to send an SMS message
SMS_SHUTDOWN_COMMANDS                       = ['END', 'STOP', 'QUIT']       # List of SMS shutdown commands for Mirror Trader

# US/Canada cell carriers dictionary
CARRIERS                                    = {
                                                # US Carriers
                                                "alltel"        : "@mms.alltelwireless.com",
                                                "att"           : "@mms.att.net",
                                                "boost"         : "@myboostmobile.com",
                                                "cricket"       : "@mms.cricketwireless.net",
                                                "p_fi"          : "msg.fi.google.com",
                                                "sprint"        : "@pm.sprint.com",
                                                "tmobile"       : "@tmomail.net",
                                                "us_cellular"   : "@mms.uscc.net",
                                                "verizon"       : "@vtext.com",
                                                "virgin"        : "@vmpix.com",

                                                # Canada Carriers
                                                "bell"          : "@txt.bell.ca",
                                                "chatr"         : "@fido.ca",
                                                "fido"          : "@fido.ca",
                                                "freedom"       : "@txt.freedommobile.ca",
                                                "koodo"         : "@msg.koodomobile.com",
                                                "public_mobile" : "@msg.telus.com",
                                                "telus"         : "@msg.telus.com",
                                                "rogers"        : "@pcs.rogers.com",
                                                "sasktel"       : "@sms.sasktel.com",
                                                "speakout"      : "@pcs.rogers.com",
                                                "virgin_ca"     : "@vmobile.ca"
                                            }

# SUBJECT MESSAGES
STARTUP_MSG_SUBJECT                         = "Mirror Trader Startup"
SHUTDOWN_MSG_SUBJECT                        = "Mirror Trader Shutdown"
MSG_SUBJECT                                 = "Mirror Trader Message"
ERROR_MSG_SUBJECT                           = "Mirror Trader Error"

# SMS MESSAGES
SMS_STARTUP                                 = "Mirror Trader is active! Type ({0}/{1}/{2}) to shutdown\n".format(*SMS_SHUTDOWN_COMMANDS)
SMS_CONFIRM                                 = "Command received...processing request\n"
SMS_SHUTDOWN                                = "Mirror Trader shutting down\n"

# ERROR MESSAGES
SMS_ERROR_INVALID_CMD                       = "ERROR: Invalid command entered!\n"
SMS_ERROR_GENERAL                           = "ERROR: An unknown error occurred!\n"
