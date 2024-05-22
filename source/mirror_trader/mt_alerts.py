'''
=============================================================================
* mt_alerts.py                                                              *
=============================================================================
* This file contains the TradeAlerts class and all functions associated     *
* with the collection of option trade alerts from Discord trading channels. *
=============================================================================
'''

import os
import re
import time
import json
import pickle
import logging
import requests
import threading
import datetime as dt

from dateutil import tz
from colour import Color
from fuzzywuzzy import fuzz
from dateutil.parser import parse
from source.mirror_trader import mt_globals as glob
from source.mirror_trader import mt_misc as misc
from source.mirror_trader.mt_endpoints import DiscordEndpoints


class TradeAlerts(threading.Thread):
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes all appropriate flags, lists, and tables    *
    * used to handle the processing of option trade alerts on a single      *
    * thread. Tables and lists are created to support different trading     *
    * servers and channels on the Discord website.                          *
    *                                                                       *
    *   INPUT:                                                              *
    *         headers (dict) - Request headers used to send Discord API     *
    *                          requests.                                    *
    *         channel (dict) - The channel selected to scrape option trade  *
    *                          alerts.                                      *
    * invest_percent (float) - Percentage of account to invest in.          *
    *     SL_percent (float) - Default stop loss percentage.                *
    *           paper (bool) - Paper trade status flag to enable paper      *
    *                          trade logic for expired paper trades.        *
    *           debug (bool) - Debug status flag to view trade alert        *
    *                          details.                                     *
    *             dev (bool) - Developer mode status flag.                  *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self, headers={}, channel=[], invest_percent=0.0, SL_percent=0.0, paper=False, debug=False, dev=False):
        # Set paper, debug, developer, and network connected status
        self._paper             = paper                         # TradeAlerts paper logic status
        self._thread_debug      = debug                         # TradeAlerts debug status
        self._dev               = dev                           # TradeAlerts developer mode status
        self._network_connected = True                          # Internet connection status
        self._bot_name          = str(self.__class__.__name__)  # TradeAlerts bot name

        # If request headers or channel not provided
        if (not headers) or (not channel):

            # If headers not provided
            if not headers:
                logging.error(f"[{self._bot_name}] Need request headers to send Discord API requests!")

            # If channel not provided
            if not channel:
                logging.error(f"[{self._bot_name}] Need selected channel to search for trade alerts!")

            return None

        # Set account investment and default stop loss percentages
        self._invest_percent    = invest_percent                # Percentage of account to invest in trade
        self._default_SL        = SL_percent                    # Default stop loss percentage

        # Initialize Discord API urls and set request headers
        self._URLS              = DiscordEndpoints()            # DiscordEndpoints class containing Discord API URLS
        self._thread_headers    = headers                       # Set headers for Discord API calls

        # Set Regex filters
        self._ticker_filter     = re.compile("(?![A-Z]+:|[A-Z][a-z]+)[A-Z]+")
        self._strike_filter     = re.compile("(\\d+[.,]+[\\s]*\\d+|[.,]+[\\s]*\\d+)|(\\d+)")
        self._direction_filter  = re.compile("(?![A-Z]+:)(CALL|PUT|C|P)", flags=re.IGNORECASE)
        self._price_filter      = re.compile("(\\d+[.,]+[\\s]*\\d+|[.,]+[\\s]*\\d+)")
        self._exp_date_filter   = re.compile("(week\\w+|\\d+DTE|tomorrow|today)|(\\d+\\/\\d+\\/\\d+|\\d+\\/\\d+)|((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\w+)", flags=re.IGNORECASE)
        self._stop_filter       = re.compile("(\\d+[.,]+[\\s]*\\d+|[.,]+[\\s]*\\d+)|(\\d*%)")
        self._trade_risk_filter = re.compile("[(\\W)?.*]day.\\w+|scalp", flags=re.IGNORECASE)
        self._sell_amnt_filter  = re.compile(f"(stop[.\\w+|.\\W+]|sl[.\\w+|.\\W+]|all[.\\w+|.\\W+]|out[.\\w+|.\\W+]|profit[.\\w+|.\\W+]|remaining[.\\w+|.\\W+])|(another|most|half|some|las[.\\w+|.\\W+]|{'|'.join(glob.NUMERIC_STRINGS)})|(\\d+[.,\\/]\\d+|\\d+)", flags=re.IGNORECASE)
        
        # Initialize channels accessed and active channel
        self._channels          = channel
        self._active_channel    = ""

        # Create trade and expired trade tracker containers to manage option trade alerts from channel
        self._trade_tracker     = {}                            # Dictionary of tracked alerts from channel(s)
        self._exp_trade_tracker = {}                            # Dictionary of expired tracked alerts from channel(s)
        
        # Initialize channel thread
        threading.Thread.__init__(self)                         # Initialize thread
        self.setName(name=self._bot_name)                       # Set name of thread to channel 
        self.setDaemon(True)                                    # Set thread as background task

        return



    '''
    =========================================================================
    * run()                                                                 *
    =========================================================================
    * This function will be executed when the DiscordThread start()         *
    * method is called for a given channel thread.                          *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def run(self):
        
        # If developer mode not enabled
        if not self._dev:
            self.search_channel_trades()

        # Else thread debugging enabled
        else:
            self.search_channel_trades_debug()

        return



    '''
    =========================================================================
    * search_channel_trades()                                               *
    =========================================================================
    * This function will search a trading channel for option trade alerts.  *
    * When a valid alert is collected, the alert will get placed into the   *
    * MirrorTrader program queue.                                           *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def search_channel_trades(self):
        
        # Initialize message history table
        message_history = {}
        for channel in self._channels:
            message_history[channel['Name']] = {"prevTimestamp": None, "prevContent": ""}

        # Initialize index to current channel and previous response code
        current_channel_idx     = 0
        prev_response_code      = 0
        
        # Setup trade tracker list
        self.load_trade_tracker()

        logging.info(f"[{self._bot_name}] Beginning search for trades. . .")

        try:
            # Loop while market open and network connection is established
            while (glob.MARKET_OPEN.is_set()) and (self._network_connected):

                # NOTE: Sleep for 500 ms (0.5 seconds) before sending request (Max 50 requests per second)
                time.sleep(0.5)

                # Get current channel to process and increment channel index
                channel = self._channels[current_channel_idx]
                self._active_channel = channel['Name']
                current_channel_idx += 1

                # Reset channel index
                if current_channel_idx >= len(self._channels):
                    current_channel_idx = 0

                # Get previous message timestamp and content
                prev_message_timestamp = message_history[self._active_channel]["prevTimestamp"]
                prev_message_content = message_history[self._active_channel]["prevContent"]

                try:
                    # Request and get the last message from channel
                    response = requests.get(self._URLS.channel_messages(channel['Id'], 1), headers=self._thread_headers)
                    result = response.json()
                    response.close()

                # *** Connection Error / JSON Decode Error ***
                except (requests.exceptions.ConnectionError, json.decoder.JSONDecodeError):
                    # Verify internet connection
                    self._network_connected = misc.is_network_connected()

                    # If no internet connection established
                    if not self._network_connected:
                        
                        # Wait for connection to re-establish
                        self._network_connected = misc.wait_for_network_connection()

                    # Else internet connection established (other issue)
                    else:

                        # If Discord API rate limit
                        if response.status_code == 429:
                            
                            # If global rate limited
                            if result['global']:
                                logging.warning(f"[{self._bot_name}] Too many requests! . . . {result['message']}")

                            # Wait for <retry_after> seconds before sending new request to API
                            time.sleep(result['retry_after'])

                        # Else other issue
                        else:

                            # If new response code received
                            if (prev_response_code != response.status_code) and (response.status_code >= 300):

                                logging.warning(f"[{self._bot_name}] HTTP Response ({response.status_code}): {misc.http_response_codes(code=response.status_code)}")
                                prev_response_code = response.status_code
                    
                    # Return to beginning of while-loop
                    continue

                # *** Unknown Error ***
                except Exception:
                    logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

                    # Return to beginning of while-loop
                    continue


                # If successful request
                if response.status_code == 200:

                    # If channel message(s) collected
                    if result:

                        # Get message details and process
                        new_message_collected = result[0]
                        processed_message = self.process_message(message=new_message_collected)

                        # If new message collected (process messages sent today)
                        if (processed_message["Date"] == dt.date.today()) and \
                        (processed_message["Time"] and prev_message_timestamp != processed_message["Time"]) and \
                        (processed_message["Content"] and prev_message_content != processed_message["Content"]):
                                
                                # If thread debugging enabled
                                if self._thread_debug:
                                    logging.info(f"[{self._bot_name} ({self._active_channel})] (DEBUG) PREV TIME: {prev_message_timestamp} | PREV CONTENT: {prev_message_content}")
                                    logging.info(f"[{self._bot_name} ({self._active_channel})] (DEBUG) NEW TIME: {processed_message['Time']} | NEW CONTENT: {processed_message['Content']}")
                                
                                # If signal of new message is BTO or STC
                                if processed_message["Signal"] and processed_message["Signal"] != "N/A":

                                    # Process trade alert
                                    trade_alert = self.process_trade_alert(signal=processed_message["Signal"],
                                                                        author=processed_message["Author"],
                                                                        content=processed_message["Content"])

                                    # If valid trade alert, add to program queue
                                    if trade_alert['Signal']:
                                        queue_item = {self._active_channel : trade_alert}
                                        glob.PROGRAM_QUEUE.put(queue_item)

                                # Else new message is not a trade alert
                                else:
                                    logging.info(f"[{self._bot_name} ({self._active_channel})] No trade alert found!")

                                # Update message timestamp and content
                                message_history[self._active_channel]["prevTimestamp"] = processed_message["Time"]
                                message_history[self._active_channel]["prevContent"] = processed_message["Content"]

                    # Else no channel message(s) collected
                    else:
                        logging.warning(f"[{self._bot_name} ({self._active_channel})] No channel messages found!")

                # If paper trading and there are expired paper trades
                if (self._paper) and (self._exp_trade_tracker[self._active_channel]):

                    # Get an expired trade from the expired trades list
                    exp_trade = self._exp_trade_tracker[self._active_channel].pop()

                    # Create expired trade alert
                    trade_alert = {}
                    ticker = next(iter(exp_trade))

                    trade_alert['Signal'] = "STC"
                    trade_alert['Ticker'] = ticker
                    trade_alert['Strike'] = exp_trade[ticker]['Strike']
                    trade_alert['Direction'] = exp_trade[ticker]['Direction']
                    trade_alert['Price'] = exp_trade[ticker]['Price']
                    trade_alert['ExpDate'] = exp_trade[ticker]['ExpDate']
                    trade_alert['StopLoss'] = 0.0
                    trade_alert['Info'] = {'Type': "ALL OUT", 'Percent': 1.0}

                    # Add to program queue
                    queue_item = {self._active_channel : trade_alert}
                    glob.PROGRAM_QUEUE.put(queue_item)

        # *** Keyboard Exit ***
        except KeyboardInterrupt:
            # Set program shutdown event
            if not glob.PROGRAM_SHUTDOWN.is_set():
                glob.PROGRAM_SHUTDOWN.set()

        # If thread stopped due to program shutdown
        if glob.PROGRAM_SHUTDOWN.is_set():
            logging.info(f"[{self._bot_name}] Exiting due to program shutdown!")

        # If thread stopped due to network connection
        if not self._network_connected:
            logging.info(f"[{self._bot_name}] Exiting due to network connection!")

        # Save trade tracker list to file
        self.save_trade_tracker()

        logging.info(f"[{self._bot_name}] Successfully exited thread {self.getName()}!")

        return



    '''
    =========================================================================
    * search_channel_trades_debug()                                         *
    =========================================================================
    * This function will search a trading channel for option trade alerts.  *
    * When a valid alert is collected, the alert will get placed into the   *
    * MirrorTrader program queue.                                           *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def search_channel_trades_debug(self):
        # Initialize previous message timestamp and content
        prev_message_timestamp  = None
        prev_message_content    = ""

        # Initialize previous response code
        prev_response_code      = 0

        # Setup trade tracker list
        self.load_trade_tracker()

        logging.info(f"[{self._bot_name}] Beginning search for trades. . .")

        try:
            # Loop through selected trade channels
            for trade_channel in self._channels:

                # Request <DISCORD_CHANNEL_MESSAGE_LIMIT> messages to test
                response = requests.get(self._URLS.channel_messages(trade_channel['Id']), headers=self._thread_headers)
                result = response.json()
                response.close()

                # If successful request
                if response.status_code == 200:

                    # If channel message(s) collected
                    if result:
                        # Set active channel
                        self._active_channel = trade_channel['Name']

                        # Iterate through each channel message (oldest to newest message)
                        messages_collected = result
                        for channel_message in reversed(messages_collected):

                            # Get message details and process
                            processed_message = self.process_message(message=channel_message)

                            logging.info(f"[{self._bot_name} ({self._active_channel})]\nORIGINAL TRADE ALERT:\n" +
                                         f"\tDATE: {processed_message['Date']}\n" +
                                         f"\tTIME: {processed_message['Time']}\n" +
                                         f"\tCONTENT:\n\t{processed_message['Content']}\n\n")

                            # If new message collected
                            if (processed_message["Time"] and prev_message_timestamp != processed_message["Time"]) and \
                               (processed_message["Content"] and prev_message_content != processed_message["Content"]):
                                    
                                    # If signal of new message is BTO or STC
                                    if processed_message["Signal"] and processed_message["Signal"] != "N/A":

                                        # Process trade alert
                                        trade_alert = self.process_trade_alert(signal=processed_message["Signal"], 
                                                                               author=processed_message["Author"], 
                                                                               content=processed_message["Content"])

                                        logging.info(f"[{self._bot_name} ({self._active_channel})]\nNEW TRADE ALERT:\n" +
                                                    f"\tSIGNAL: {trade_alert['Signal']}\n" +
                                                    f"\tTICKER: {trade_alert['Ticker']}\n" +
                                                    f"\tSTRIKE: {trade_alert['Strike']}\n" +
                                                    f"\tDIRECTION: {trade_alert['Direction']}\n" +
                                                    f"\tPRICE: {trade_alert['Price']}\n" +
                                                    f"\tEXPDATE: {trade_alert['ExpDate']}\n" +
                                                    f"\tSTOPLOSS: {trade_alert['StopLoss']}\n" +
                                                    f"\tTRADE-TYPE: {trade_alert['Info']['Type']}\n" +
                                                    f"\tTRADE-PERCENT: {trade_alert['Info']['Percent']}\n\n")

                                        # If valid trade alert, add to program queue
                                        if trade_alert['Signal']:
                                            queue_item = {self._active_channel : trade_alert}
                                            glob.PROGRAM_QUEUE.put(queue_item)

                                    # Else new message is not a trade alert
                                    else:
                                        logging.info(f"[{self._bot_name} ({self._active_channel})] No trade alert found!")

                                    # Update message timestamp and content
                                    prev_message_timestamp = processed_message["Time"]
                                    prev_message_content = processed_message["Content"]

                    # Else no channel message(s) collected
                    else:
                        logging.warning(f"[{self._bot_name} ({self._active_channel})] No channel messages found!")

                # Else unsuccessful request
                else:

                    # If Discord API rate limit
                    if response.status_code == 429:
                        
                        # If global rate limited
                        if result['global']:
                            logging.warning(f"[{self._bot_name}] Too many requests: {result['message']}")

                        # Wait for <retry_after> seconds before sending new request to API
                        time.sleep(result['retry_after'])

                    # Else other issue
                    else:

                        # If new response code received
                        if (prev_response_code != response.status_code) and (response.status_code >= 300):

                            logging.warning(f"[{self._bot_name}] HTTP Response ({response.status_code}): {misc.http_response_codes(code=response.status_code)}")
                            prev_response_code = response.status_code

        # *** Keyboard Exit ***
        except KeyboardInterrupt:
            pass

        logging.info(f"[{self._bot_name}] Exiting channel trades debug!")

        # Place exit keyword in queue for channel trades debug
        queue_item = {self.getName() : "END_DEBUG"}
        glob.PROGRAM_QUEUE.put(queue_item)

        return



    #############################################################
    #   E X E C U T I V E   C H A N N E L   F U N C T I O N S   #
    #############################################################
    '''
    =========================================================================
    * process_trade_alert()                                                 *
    =========================================================================
    * This function will take a Discord channel message and process it to   *
    * extract a ticker, strike price, direction, price, and exp. date.      *
    *                                                                       *
    *   INPUT:                                                              *
    *          signal (str) - Buy To Open (BTO) or Sell To Close (STC).     *
    *          author (str) - The author of the message being processed.    *
    *         content (str) - The message content/text.                     *
    *                                                                       *
    *   OUPUT:                                                              *
    *         trade_info (dict) - A dictionary containing the following:    *
    *          +             Signal (str) - 'BTO' or 'STC' signal.          *
    *          +             Ticker (str) - Stock ticker symbol.            *
    *          +             Strike (str) - Strike price of the contract.   *
    *          +          Direction (str) - 'Call' or 'Put' direction.      *
    *          +            Price (float) - Price of the contract.          *
    *          + Exp Date (datetime.date) - Exp. date of the contract.      *
    *          +        Stop Loss (float) - Stop loss price.                *
    *          +              Info (dict) - Dictionary containing the risk  *
    *                                       type and percent to invest/sell.*
    =========================================================================
    '''
    def process_trade_alert(self, signal="", author="", content=""):
        # Initialize option trade information dictionary and set as invalid return type
        trade_info = {
            "Signal": "",
            "Ticker": "",
            "Strike": "",
            "Direction": "",
            "Price": 0.0,
            "ExpDate": dt.date.today(),
            "StopLoss": 0.0,
            "Info": {"Type": "", "Percent": 0.0}
        }
        invalid_trade_info = trade_info.copy()

        # NOTE: Skip vertical trade alerts
        if "VERTICAL" in content.upper():
            logging.warning(f"[{self._bot_name} ({self._active_channel})] Ignoring vertical trade alert!")
            return invalid_trade_info

        # NOTE: Skip common stock trade alerts
        if "COMMON" in content.upper():
            logging.warning(f"[{self._bot_name} ({self._active_channel})] Ignoring common stock trade alert!")
            return invalid_trade_info


        # *************************************************************************
        # * B U Y   T O   O P E N   (B T O)   S I G N A L   P R O C E S S I N G   *
        # *************************************************************************
        if signal.upper() == "BTO":
            # Set trade signal
            trade_info['Signal'] = signal

            # ==========================
            #   TICKER
            # ==========================
            # Search for ticker symbol
            ticker = self._ticker_filter.search(content)

            # If ticker found
            if bool(ticker):
                
                # Set ticker symbol
                trade_info['Ticker'] = ticker.group()

                # Remove ticker from alert
                content = self._ticker_filter.sub("", content, 1).strip()
            
            # Else ticker not found
            else:
                logging.error(f"[{self._bot_name} ({self._active_channel})] Ticker not found!")
                return invalid_trade_info

            # ==========================
            #   STRIKE
            # ==========================
            # Search for strike price
            strike = self._strike_filter.search(content)

            # If strike price found
            if bool(strike):

                # Get strike price
                strike_found = strike.group()

                # Fix typo(s) (if any)
                # Typo Case 1: 12. 5 --> 12.5 (whitespace added)
                if " " in strike_found:
                    strike_found = strike_found.replace(" ", "")

                # Typo Case 2: 12,5 --> 12.5 (',' instead of '.')
                if ',' in strike_found:
                    strike_found = strike_found.replace(",", ".")

                # Typo Case 3: 12..5 --> 12.5 (multiple '.' instead of single '.')
                if strike_found.count(".") > 1:
                    strike_found = strike_found.replace(".", "", strike_found.count(".") - 1)

                # Set strike price
                trade_info['Strike'] = str(strike_found)

                # Remove strike from alert
                content = self._strike_filter.sub("", content, 1).strip()

            # Else strike price not found
            else:
                logging.error(f"[{self._bot_name} ({self._active_channel})] Strike Price not found!")
                return invalid_trade_info

            # ==========================
            #   DIRECTION
            # ==========================
            # Search for direction
            direction = self._direction_filter.search(content)

            # If direction found
            if bool(direction):

                # Set direction
                trade_info['Direction'] = direction.group().lower()

                # If direction is single letter call ('c')
                if trade_info['Direction'] == 'c':
                    trade_info['Direction'] = 'call'

                # Else if direction is single letter put ('p')
                elif trade_info['Direction'] == 'p':
                    trade_info['Direction'] = 'put'

                # Remove direction alert
                content = self._direction_filter.sub("", content, 1).strip()

            # Else direction not found
            else:
                logging.error(f"[{self._bot_name} ({self._active_channel})] Direction not found!")
                return invalid_trade_info
            
            # ==========================
            #   PRICE
            # ==========================
            # Search for price
            price = self._price_filter.search(content)

            # If price found
            if bool(price):
                
                # Get price
                price_found = price.group()

                # Fix typo(s) (if any)
                # Type Case 1: 1. 34 --> 1.34 (whitespace added)
                if " " in price_found:
                    price_found = price_found.replace(" ", "")

                # Typo Case 2: 1,34 --> 1.34 (',' instead of '.')
                if ',' in price_found:
                    price_found = price_found.replace(",", ".")

                # Typo Case 3: 1..34 --> 1.34 (multiple '.' instead of single '.')
                if price_found.count(".") > 1:
                    price_found = price_found.replace(".", "", price_found.count(".") - 1)

                # Set price
                trade_info['Price'] = round(float(price_found), 2)

                # Remove price from alert
                content = self._price_filter.sub("", content, 1).strip()

            # Else price not found
            else:
                logging.error(f"[{self._bot_name} ({self._active_channel})] Price not found!")
                return invalid_trade_info

            # ==========================
            #   EXP DATE
            # ==========================
            # Search for exp date
            exp_date = self._exp_date_filter.search(content)

            # If exp date found
            if bool(exp_date):
                
                # If group one (1) match (weekly/weeklys expiration date OR Today expiration date OR Tomorrow expiration date)
                if exp_date.group(1):

                    # If weekly/weeklys expiration date
                    if "WEEK" in exp_date.group(1).upper():
                        
                        # Set expiration date to upcoming Friday
                        trade_info['ExpDate'] = dt.date.today() + dt.timedelta(days=(((4 - dt.date.today().weekday()) + 7) % 7))

                    # Else if tomorrow expiration date
                    elif "TOMORROW" in exp_date.group(1).upper():

                        # Set expiration date to next day
                        trade_info['ExpDate'] = dt.date.today() + dt.timedelta(days=1)

                    # Else if (#)DTE expirtaion date
                    elif "DTE" in exp_date.group(1).upper():
                        
                        # Get number of days till expiration
                        days_till_exp = int(re.match("\\d+", exp_date.group(1)).group())
                        
                        # Set expiration date
                        trade_info['ExpDate'] = dt.date.today() + dt.timedelta(days=days_till_exp)

                # Else if group two (2) match (numerical expiration date)
                elif exp_date.group(2):
                    # Get expiration date
                    trade_info['ExpDate'] = parse(exp_date.group(2)).date()

                    # # If expiration date found is before today's date
                    # if trade_info['ExpDate'] < dt.date.today():
                        
                    #     # Set expiration date to next year
                    #     trade_info['ExpDate'] = trade_info['ExpDate'] + relativedelta(years=1)

                # Else if group three (3) match (string month expiration date)
                elif exp_date.group(3):
                    
                    # Get the month number (1-12)
                    month_number = parse(exp_date.group(3)).month
                    
                    # Set expiration date to first day of the month
                    trade_info['ExpDate'] = dt.date(dt.date.today().year, month_number, 1)

                    # # If expiration date found is before today's expiration date
                    # if trade_info['ExpDate'] < dt.date.today():
                        
                    #     # Set expiration date to next year
                    #     trade_info['ExpDate'] = trade_info['ExpDate'] + relativedelta(years=1)

                # Else default
                else:
                    # NOTE: Exp date already initialized to today's date
                    pass


                # Remove expiration date from alert
                content = self._exp_date_filter.sub("", content, 1).strip()


            # else exp date not found
            else:
                # NOTE: Exp date already initialized to today's date
                pass

            # Add trade alert to trade tracker list
            self._trade_tracker[self._active_channel].append(
                {
                    trade_info['Ticker']:
                    {
                        "AlertTime": time.time(),
                        "Strike": trade_info['Strike'],
                        "Direction": trade_info['Direction'],
                        "Price": trade_info['Price'],
                        "ExpDate": trade_info['ExpDate']
                    }
                }
            )

            # ==========================
            #   STOP LOSS
            # ==========================
            # Search for stop loss
            stop_loss = self._stop_filter.search(content)
            
            # If stop loss found
            if bool(stop_loss):

                # If group one (1) match (stop loss price)
                if stop_loss.group(1):

                    # Get stop loss price
                    stop_price_found = stop_loss.group(1)

                    # Fix typo(s) (if any)
                    # Typo Case 1: 1. 34 --> 1.34 (whitespace added)
                    if " " in stop_price_found:
                        stop_price_found = stop_price_found.replace(" ", "")

                    # Typo Case 2: 1,34 --> 1.34 (',' instead of '.')
                    if ',' in stop_price_found:
                        stop_price_found = stop_price_found.replace(",", ".")

                    # Typo Case 3: 1..34 --> 1.34 (multiple '.' instead of single '.')
                    if stop_price_found.count(".") > 1:
                        stop_price_found = stop_price_found.replace(".", "", stop_price_found.count(".") - 1)

                    # Set stop price
                    stop_price = round(float(stop_price_found), 2)

                    # If stop price found in alert is not at least 20% (typo correction)
                    if (1.0 - (stop_price / trade_info['Price'])) < self._default_SL:

                        # Set a default stop loss value
                        stop_price = round(trade_info['Price'] - (trade_info['Price'] * self._default_SL), 2)

                    # Set stop loss price
                    trade_info['StopLoss'] = stop_price


                # Else if group two (2) match (stop loss percent)
                elif stop_loss.group(2):

                    # Get stop loss percent
                    stop_percent_found = int(stop_loss.group(2).replace("%","")) / 100

                    # Calculate stop loss price from stop loss percent
                    trade_info['StopLoss'] = round(trade_info['Price'] - (trade_info['Price'] * stop_percent_found), 2)

                # Else set a default variable stop loss value
                else:
                    # Determine the number of months till trade expiration date
                    months_till_exp = (trade_info['ExpDate'].year - dt.date.today().year) * 12 + (trade_info['ExpDate'].month - dt.date.today().month)
                    
                    # If more than one month till trade expiration date
                    if months_till_exp > 1:

                        # Add 7.27% to stop loss percent for every month
                        stop_loss_percent = self._default_SL + (months_till_exp * 0.0727)

                        # If stop loss percent greater than 100%
                        if stop_loss_percent > 1.0:

                            # Set stop loss percent to 100%
                            stop_loss_percent = 1.0
                    
                    # Else less than one month till trade expiration date
                    else:

                        # Set stop loss percent to default value
                        stop_loss_percent = self._default_SL
                    
                    trade_info['StopLoss'] = round(trade_info['Price'] - (trade_info['Price'] * stop_loss_percent), 2)

                # Remove stop price/percent from alert
                content = self._stop_filter.sub("", content, 1).strip()
            
            # Else stop loss not found
            else:
                # Set a default variable stop loss value
                # Determine the number of months till trade expiration date
                months_till_exp = (trade_info['ExpDate'].year - dt.date.today().year) * 12 + (trade_info['ExpDate'].month - dt.date.today().month)
                
                # If more than one month till trade expiration date
                if months_till_exp > 1:

                    # Add 7.27% to stop loss percent for every month
                    stop_loss_percent = self._default_SL + (months_till_exp * 0.0727)

                    # If stop loss percent greater than 100%
                    if stop_loss_percent > 1.0:

                        # Set stop loss percent to 100%
                        stop_loss_percent = 1.0
                
                # Else less than one month till trade expiration date
                else:

                    # Set stop loss percent to default value
                    stop_loss_percent = self._default_SL

                trade_info['StopLoss'] = round(trade_info['Price'] - (trade_info['Price'] * stop_loss_percent), 2)

            # ==========================
            #   TRADE RISK
            # ==========================
            # Search for trade risk
            trade_risk = self._trade_risk_filter.search(content)

            # If trade risk found
            if bool(trade_risk):

                # Set 'Daytrade' risk level and default percent to invest
                trade_info['Info']['Type'] = "DAYTRADE/SCALP"
                trade_info['Info']['Percent'] = self._invest_percent

            # Else trade risk not found
            else:

                # Set 'Risky' risk level and 30% reduction in default percent to invest
                trade_info['Info']['Type'] = "RISKY/SWING"
                trade_info['Info']['Percent'] = self._invest_percent - (self._invest_percent * 0.3)



        # *****************************************************************************
        # * S E L L   T O   C L O S E   (S T C)   S I G N A L   P R O C E S S I N G   *
        # *****************************************************************************
        if signal.upper() == "STC":
            
            # Set trade signal
            trade_info['Signal'] = signal

            # Find stock ticker in sell alert
            ticker = self._ticker_filter.search(content)

            # If stock ticker found in alert AND ticker is not "STOP" AND ticker is not found at the end of the message content
            if (bool(ticker)) and ("STOP" not in ticker.group()) and ((ticker.span()[0] / len(content)) < 0.75):

                # Set ticker and remove from alert
                trade_info['Ticker'] = ticker.group()
                content = self._ticker_filter.sub("", content, 1).strip()

                # Search for trade match for ticker
                trade_match = self.find_trade_match(ticker=trade_info['Ticker'])

                # If not matching trade found
                if not trade_match:
                    return invalid_trade_info

            # Else stock ticker not found in alert
            else:

                # If trade tracker list is not empty
                if self._trade_tracker[self._active_channel]:

                    # Get the most recent trade
                    alert_times = [trade[next(iter(trade))]['AlertTime'] for trade in self._trade_tracker[self._active_channel]]
                    trade_match = next(trade for trade in self._trade_tracker[self._active_channel] if trade[next(iter(trade))]['AlertTime'] == max(alert_times))

                # Else trade tracker list is empty
                else:
                    logging.warning(f"[{self._bot_name} ({self._active_channel})] Trade Tracker list is empty!")
                    return invalid_trade_info

            # Set Ticker, Strike, Direction, and Expiration Date
            trade_info['Ticker'] = next(iter(trade_match))
            trade_info['Strike'] = trade_match[trade_info['Ticker']]['Strike']
            trade_info['Direction'] = trade_match[trade_info['Ticker']]['Direction']
            trade_info['ExpDate'] = trade_match[trade_info['Ticker']]['ExpDate']

            # Remove Strike, Direction, and Expiration Date from alert
            if "EVA" in author.upper():
                content = self._strike_filter.sub("", content, 1).strip()
                content = self._direction_filter.sub("", content, 1).strip()
                content = self._exp_date_filter.sub("", content, 1).strip()

            # If selling at break-even price
            if ("AT EVEN" in content.upper()) or ("AT BREAK EVEN" in content.upper()):

                # Set breakeven price and remove price from alert
                trade_info['Price'] = trade_match[trade_info['Ticker']]['Price']
                content = self._price_filter.sub("", content, 1).strip()

            # Else not selling at break-even price
            else:

                # Search for price
                price = self._price_filter.search(content)

                # If price found
                if bool(price):
                    
                    # Get price
                    price_found = price.group()

                    # Fix typo(s) (if any)
                    # Typo Case 1: 1. 34 --> 1.34 (whitespace added)
                    if " " in price_found:
                        price_found = price_found.replace(" ", "")

                    # Typo Case 2: 1,34 --> 1.34 (',' instead of '.')
                    if ',' in price_found:
                        price_found = price_found.replace(",", ".")

                    # Typo Case 3: 1..34 --> 1.34 (multiple '.' instead of single '.')
                    if price_found.count(".") > 1:
                        price_found = price_found.replace(".", "", price_found.count(".") - 1)

                    # Set price
                    trade_info['Price'] = round(float(price_found), 2)

                    # Remove price from alert
                    content = self._price_filter.sub("", content, 1).strip()

            # Update the trade timestamp of the matched trade and replace in the trade tracker list
            trade_match[trade_info['Ticker']]['AlertTime'] = time.time()
            trade_match_index = self._trade_tracker[self._active_channel].index(trade_match)
            self._trade_tracker[self._active_channel][trade_match_index] = trade_match

            # Determine percentage amount to sell
            sell_amount = self._sell_amnt_filter.search(content)

            # If sell amount found
            if bool(sell_amount):

                # If group one (1) match (stop loss hit)
                if sell_amount.group(1):
                    trade_info['Info']['Type'] = "ALL OUT"
                    trade_info['Info']['Percent'] = glob.SELL_ALL_PERCENT

                # Else if group two (2) match (word sequence)
                elif sell_amount.group(2):

                    # If numeric string match
                    if sell_amount.group(2).upper() in glob.NUMERIC_STRINGS:

                        # Get numeric value of numeric string
                        numeric_value = glob.NUMERIC_STRINGS.index(sell_amount.group(2).upper()) + 1

                        trade_info['Info']['Type'] = "SPECIFIC"
                        trade_info['Info']['Percent'] = round((numeric_value / 100), 2)

                    # Else word match
                    else:

                        # If sell MOST
                        if "MOST" in sell_amount.group(2).upper():

                            # Sell 75% of option contracts held
                            trade_info['Info']['Type'] = "MOST"
                            trade_info['Info']['Percent'] = glob.SELL_MOST_PERCENT

                        # Else if sell HALF
                        elif "HALF" in sell_amount.group(2).upper():

                            # Sell 50% of option contracts held
                            trade_info['Info']['Type'] = "HALF"
                            trade_info['Info']['Percent'] = glob.SELL_HALF_PERCENT

                        # Else if sell SOME
                        elif "SOME" in sell_amount.group(2).upper():
                            
                            # Sell 25% of option contracts held
                            trade_info['Info']['Type'] = "SOME"
                            trade_info['Info']['Percent'] = glob.SELL_SOME_PERCENT

                        # Else if sell SINGLE
                        elif "ANOTHER" in sell_amount.group(2).upper():

                            # Sell single option contract
                            trade_info['Info']['Type'] = "SINGLE"
                            trade_info['Info']['Percent'] = glob.SELL_ANOTHER_PERCENT

                        # Else default
                        else:

                            # Sell 100% of option contracts held
                            trade_info['Info']['Type'] = "ALL OUT"
                            trade_info['Info']['Percent'] = glob.SELL_ALL_PERCENT


                # Else if group three (3) match (numeric match)
                elif sell_amount.group(3):
                    
                    # Fix typo(s) in fractional sell amount (if any)
                    sell_value = re.sub("[^\\w\\s\\/]", "/", sell_amount.group(3)).strip()

                    # If fractional sell amount
                    if "/" in sell_value:

                        # Get the numerator and denominator of fractional sell value
                        num, den = sell_value.split('/')
                        num = int(num)
                        den = int(den)

                        # If invalid denominator and valid numerator values
                        if (den < 1) and (num > 0):
                            den = num + round((num - 1) / 2)

                        # Else if invalid numerator and valid denominator values
                        elif (num < 1) and (den > 0):
                            num = den - round((den - 1) / 2)

                        # Else invalid numerator and denominator values
                        elif (num < 1) and (den < 1):
                            # Default to 1/2
                            num = 1
                            den = 2

                        trade_info['Info']['Type'] = "FRACTIONAL"
                        trade_info['Info']['Percent'] = round((num / den), 2)

                    # Else numeric sell amount
                    else:
                        trade_info['Info']['Type'] = "SPECIFIC"
                        trade_info['Info']['Percent'] = round((int(sell_value) / 100), 2)

                # Else default
                else:

                    # Sell 100% of option contracts held
                    trade_info['Info']['Type'] = "ALL OUT"
                    trade_info['Info']['Percent'] = glob.SELL_ALL_PERCENT

                # Remove sell amount from alert
                content = self._sell_amnt_filter.sub("", content, 1).strip()

            # Else sell amount not found
            else:

                # Sell 100% of option contracts held
                trade_info['Info']['Type'] = "ALL OUT"
                trade_info['Info']['Percent'] = glob.SELL_ALL_PERCENT

            
            # Remove trade from trade tracker list if type is "ALL OUT"
            if trade_info['Info']['Type'] == "ALL OUT":
                trade_to_remove = next(trade for trade in self._trade_tracker[self._active_channel] if trade_info['Ticker'] in trade.keys() and
                                                                                          trade_info['Strike'] == trade[trade_info['Ticker']]['Strike'] and
                                                                                          trade_info['Direction'] == trade[trade_info['Ticker']]['Direction'] and
                                                                                          trade_info['ExpDate'] == trade[trade_info['Ticker']]['ExpDate'])
                self._trade_tracker[self._active_channel].remove(trade_to_remove)

                # If thread debugging enabled
                if self._thread_debug:
                    logging.info(f"[{self._bot_name} ({self._active_channel})] (DEBUG) Trade Tracker List: {self._trade_tracker[self._active_channel]}")


        # If paper trading and SPX trade alerted
        if (self._paper) and (trade_info['Ticker'] == "SPX"):
            logging.warning(f"[{self._bot_name} ({self._active_channel})] Cannot trade 'SPX' with paper trading account!")
            return invalid_trade_info


        return trade_info



    ###################################
    #   M I S C   F U N C T I O N S   #
    ###################################
    '''
    =========================================================================
    * find_trade_match()                                                    *
    =========================================================================
    * This function will take a stock ticker and search for it within a     *
    * Discord channel trade tracker list.                                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         ticker (string) - The ticker symbol to search for in the      *
    *                           trade tracker list.                         *
    *                                                                       *
    *   OUPUT:                                                              *
    *      trade_match (dict) - The matching trade alert from the channel   *
    *                           trade tracker list.                         *
    =========================================================================
    '''
    def find_trade_match(self, ticker=""):
        # If no ticker provided
        if not ticker:
            logging.error(f"[{self._bot_name} ({self._active_channel})] No ticker provided to search for!")
            return None

        # Find all trades associated with ticker in trade tracker list
        matching_trades = [trade for trade in self._trade_tracker[self._active_channel] if ticker in trade.keys()]

        # If trade(s) found
        if matching_trades:

            # If more than one trade found
            if len(matching_trades) > 1:

                # Get the most recent trade
                alert_times = [trade[ticker]['AlertTime'] for trade in matching_trades]
                trade_match = next(trade for trade in matching_trades if trade[ticker]['AlertTime'] == max(alert_times))

            # Else only one trade found
            else:
                trade_match = matching_trades.pop()

        # Else trade(s) not found
        else:

            # If there are trades in the trade tracker list
            if self._trade_tracker[self._active_channel]:

                # Check if ticker symbol from alert is possibly mispelled
                trade_tracker_tickers = list(set().union(*(trade.keys() for trade in self._trade_tracker[self._active_channel])))
                ticker_match = self.find_matching_ticker(ticker, trade_tracker_tickers)

                # If match found for ticker
                if ticker_match:

                    # Find all trades associated with ticker in trade tracker list
                    matching_trades = [trade for trade in self._trade_tracker[self._active_channel] if ticker_match in trade.keys()]

                    # If trade(s) found
                    if matching_trades:

                        # If more than one trade found
                        if len(matching_trades) > 1:

                            # Get the most recent trade
                            alert_times = [trade[ticker_match]['AlertTime'] for trade in matching_trades]
                            trade_match = next(trade for trade in matching_trades if trade[ticker_match]['AlertTime'] == max(alert_times))

                        # Else only one trade found
                        else:
                            trade_match = matching_trades.pop()
                    
                    # Else no trade(s) found
                    else:
                        logging.error(f"[{self._bot_name} ({self._active_channel})] No trades found for {ticker_match}!")
                        return None

                # Else no match found for ticker
                else:
                    
                    # If "Stopped Out" signal
                    if "STOP" in ticker.upper():

                        # If more than one trade available in trade tracker list
                        if len(self._trade_tracker[self._active_channel]) > 1:

                            # Get the most recent trade
                            alert_times = [trade[next(iter(trade))]['AlertTime'] for trade in self._trade_tracker[self._active_channel]]
                            trade_match = next(trade for trade in self._trade_tracker[self._active_channel] if trade[next(iter(trade))]['AlertTime'] == max(alert_times))

                        # Else only one trade found
                        else:
                            trade_match = self._trade_tracker[self._active_channel].pop()

                    # Else not stopped out signal
                    else:
                        logging.error(f"[{self._bot_name} ({self._active_channel})] No ticker match found for {ticker}!")
                        return None

            # Else trade tracker list is empty
            else:
                logging.warning(f"[{self._bot_name} ({self._active_channel})] Trade Tracker list is empty!")
                return None

        # Return the matching trade alert for search ticker
        return trade_match



    '''
    =========================================================================
    * process_message()                                                     *
    =========================================================================
    * This function will take a Discord channel message and process it to   *
    * extract a date, timestamp, author, signal, and content.               *
    *                                                                       *
    *   INPUT:                                                              *
    *         message (dict) - Discord channel message.                     *
    *                                                                       *
    *   OUPUT:                                                              *
    *         processed_dict (dict) - A dictionary containing:              *
    *           1.) Date (datetime.date) - The date of the message.         *
    *           2.) Time (datetime.time) - The timestamp of the message.    *
    *           3.)         Author (str) - The author of the message.       *
    *           4.)         Signal (str) - A 'BTO' or 'STC' signal.         *
    *           5.)        Content (str) - The message content/text.        *
    =========================================================================
    '''
    def process_message(self, message={}):
        # Initialize processed message dictionary
        processed_dict = {
            'Date': None, 
            'Time': None, 
            'Author': "", 
            'Signal': "", 
            'Content': ""
        }


        # Get message date and timestamp
        if 'timestamp' in message:
            timestamp = dt.datetime.fromisoformat(message['timestamp']).astimezone(tz.tzlocal())
            processed_dict['Date'] = timestamp.date()
            processed_dict['Time'] = timestamp.time()


        # Get message author
        if 'author' in message:
            processed_dict['Author'] = message['author']['username']


        # Get message signal (BTO / STC)
        if ('embeds' in message) and (message['embeds']):

            # If embedded type is rich text
            if message['embeds'][0]['type'].upper() == "RICH":
                
                # Get embedded message border color and determine trade signal (Green = BTO / Red = STC)
                hex_color = f"#{format(message['embeds'][0]['color'], 'x').zfill(6)}"
                signal_color = misc.get_nearest_known_color(hex_color)

                # If green color range (BTO channel message)
                if signal_color == Color("green"):
                    processed_dict['Signal'] = "BTO"

                # Else if red color range (STC channel message)
                elif signal_color == Color("red"):
                    processed_dict['Signal'] = "STC"

                # Else other color range (N/A channel message)
                else:
                    processed_dict['Signal'] = "N/A"

            # Else embedded type is not rich text
            else:
                processed_dict['Signal'] = "N/A"


        # Get message content
        # CHANNELS: Eva-alerts, Wizard-alerts, Kian-alerts, Elkan-alerts (bot active)
        if ("embeds" in message) and (message["embeds"]):

            # If embedded message type is rich text
            if message["embeds"][0]["type"].upper() == "RICH":

                # Remove all non-alphanumeric characters and "BTO/STC" text from beginning of message content (if any)
                filtered_content = re.sub("(?:^|\\W+)(BTO|STC)(?:$|\\W+)", "", message["embeds"][0]["description"], flags=re.IGNORECASE).strip()
                processed_dict['Content'] = filtered_content

        # CHANNELS: Eva-alerts, Wizard-alerts, Kian-alerts, Elkan-alerts (bot inactive)
        elif ("content" in message) and (message["content"]):

            # Determine signal if no embedded message border color
            first_word = message['content'].split()[0]
            if ("STC" in first_word.upper()) or ("STOP" in first_word.upper()) or ("SOLD" in first_word.upper()):
                processed_dict["Signal"] = "STC"

            else:
                processed_dict["Signal"] = "BTO"

            # Remove all non-alphanumeric characters and "BTO/STC" text from beginning of message content (if any)
            filtered_content = re.sub("(?:^|\\W+)(BTO|STC)(?:$|\\W+)", "", message["content"], flags=re.IGNORECASE).strip()
            processed_dict['Content'] = filtered_content


        # Remove guild tag from content if it exists
        if glob.GUILD_TAG in processed_dict["Content"]:
            processed_dict["Content"] = re.sub(glob.GUILD_TAG, "", processed_dict["Content"]).strip()

        # Remove disclaimer from content if it exists
        if "DISCLAIMER" in processed_dict["Content"]:
            stop_index = processed_dict["Content"].index("\n\n")
            processed_dict["Content"] = processed_dict["Content"][0:stop_index]

        # Convert double-whitespace to single-whitespace
        if "  " in processed_dict["Content"]:
            processed_dict["Content"] = processed_dict["Content"].replace("  ", " ")

        # # Skip "Trade Summary Recap" messages
        # if (processed_dict["Content"].count("%") > 2) or ((processed_dict["Content"].count("%") > 1) and \
        #     (sum(1 for _ in glob.EMOJI_FILTER.finditer(processed_dict["Content"])) > 1)) or (('WIN' in processed_dict["Content"].upper()) and \
        #     (('LOSER' in processed_dict["Content"].upper()) or ('LOSS' in processed_dict["Content"].upper()))):

        # Skip "Trade Summary Recap" and error messages
        if ("404 NOT FOUND" in processed_dict["Content"].upper()) or ("RECAP" in processed_dict["Content"].upper()) or \
            ((processed_dict["Content"].count("%") > 1) and (sum(1 for _ in glob.EMOJI_FILTER.finditer(processed_dict["Content"])) > 1)) or \
            (('WIN' in processed_dict["Content"].upper()) and (('LOSER' in processed_dict["Content"].upper()) or \
            ('LOSS' in processed_dict["Content"].upper()))):
            processed_dict["Signal"] = "N/A"

        return processed_dict



    '''
    =========================================================================
    * find_matching_ticker()                                                *
    =========================================================================
    * This function will attempt to match a misspelled ticker with tickers  *
    * available within a list. If a match is found, the correctly spelled   *
    * ticker will be returned.                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *         ticker_to_find (str) - The misspelled ticker.                 *
    *              tickers ([str]) - List of tickers to match the           *
    *                                misspelled ticker to.                  *
    *                                                                       *
    *   OUPUT:                                                              *
    *         ticker_match (str) - The correctly spelled ticker.            *
    =========================================================================
    '''
    def find_matching_ticker(self, ticker_to_find="", tickers=[]):
        # Initialize ticker match
        ticker_match = ""

        # Iterate through all tickers
        for ticker in tickers:

            # Determine a match ratio for the ticker being searched
            match_ratio = fuzz.ratio(ticker_to_find.upper(), ticker.upper())

            # If match ratio 80% or greater, consider the ticker a match
            if match_ratio >= 80:
                ticker_match = ticker
                break

        return ticker_match



    '''
    =========================================================================
    * load_trade_tracker()                                                  *
    =========================================================================
    * This function will load the trade channel's trade tracker list to be  *
    * used for the current trading day.                                     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def load_trade_tracker(self):

        # Loop through selected trade channels
        for trade_channel in self._channels:

            # Initialize path to trade tracker files
            trade_tracker_file = f"{glob.TRACKER_DIR}{trade_channel['Name']}{glob.TRACKER_FILE_TYPE}"

            # If developer mode enabled
            if self._dev:
                trade_tracker_file = f"{glob.TRACKER_DEBUG_DIR}{trade_channel['Name']}{glob.TRACKER_FILE_TYPE}"

            # If trade tracker file found for channel
            if os.path.exists(trade_tracker_file):

                # Open trade tracker file for reading
                with open(trade_tracker_file, "rb") as file:
                    try:
                        # Load trade tracker list
                        trade_tracker_list = pickle.load(file)

                        # Remove trades with expiration dates that are before today's date (expired trades)
                        self._exp_trade_tracker[trade_channel['Name']] = [trade for trade in trade_tracker_list if trade[next(iter(trade))]['ExpDate'] < dt.date.today()]
                        self._trade_tracker[trade_channel['Name']] = [trade for trade in trade_tracker_list if trade not in self._exp_trade_tracker[trade_channel['Name']]]

                        if self._thread_debug:
                            logging.info(f"[{self._bot_name}] (DEBUG) Found {len(self._exp_trade_tracker[trade_channel['Name']])} expired trades! ==> {self._exp_trade_tracker[trade_channel['Name']]}")

                    # *** Pickle Error ***
                    except (pickle.PickleError, pickle.UnpicklingError):
                        logging.warning(f"[{self._bot_name}] Unable to extract trade tracker values for {trade_channel['Name']} from file!")

                    # *** EOF Error ***
                    except EOFError:
                        logging.warning(f"[{self._bot_name}] Trade tracker file for {trade_channel['Name']} is empty!")

                    # *** Unknown Error ***
                    except Exception:
                        logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

                    # Initialize tracker list for trade channel
                    self._trade_tracker[trade_channel['Name']] = []

            # Else trade tracker file not found
            else:
                logging.warning(f"[{self._bot_name}] Could not find trade tracker file for {trade_channel['Name']}!")
                
                # Initialize tracker list for trade channel
                self._trade_tracker[trade_channel['Name']] = []

        return
    


    '''
    =========================================================================
    * save_trade_tracker()                                                  *
    =========================================================================
    * This function will save the trade channel's trade tracker list to be  *
    * used for the next trading day.                                        *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def save_trade_tracker(self):

        # Loop through selected trade channels
        for trade_channel in self._channels:

            # Initialize path to trade tracker files
            trade_tracker_file = f"{glob.TRACKER_DIR}{trade_channel['Name']}{glob.TRACKER_FILE_TYPE}"

            # If developer mode enabled
            if self._dev:
                trade_tracker_file = f"{glob.TRACKER_DEBUG_DIR}{trade_channel['Name']}{glob.TRACKER_FILE_TYPE}"

            # Open trade tracker file for writing
            with open(trade_tracker_file, "wb") as file:
                try:
                    # Write contents of trade tracker list to trade tracker file
                    pickle.dump(self._trade_tracker[trade_channel['Name']], file)

                    logging.info(f"[{self._bot_name}] {trade_channel['Name']} Trade Tracker list has been saved!")
                
                # *** Pickle Error ***
                except (pickle.PickleError, pickle.UnpicklingError):
                    logging.warning(f"[{self._bot_name}] Unable to save trade tracker values for {trade_channel['Name']} to file!")

                # *** Unknown Error ***
                except Exception:
                    logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)
        
        return
