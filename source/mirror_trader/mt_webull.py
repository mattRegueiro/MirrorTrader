'''
=========================================================================
* mt_webull.py                                                          *
=========================================================================
* This file contains the WebullBot class and all functions associated   *
* with stock and options trading on Webull. The WebullBot class has     *
* the capability of performing paper trading and live trading.          *
=========================================================================
'''
import os
import time
import email
import pickle
import logging
import asyncio
import requests
import threading
import email.utils
import pandas as pd
import datetime as dt
import aioimaplib as imap
import source.mirror_trader.mt_globals as glob
import source.mirror_trader.mt_misc as misc

from webull import webull               # Live-trading support
from webull import paper_webull         # Paper-trading support

from lxml import etree
from dateutil import tz
from getpass import getpass
from tabulate import tabulate
from dateutil.parser import parse

class WebullBot():
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes all appropriate flags, lists, and tables    *
    * used to handle active option trades and orders. Separate tables and   *
    * lists are created depending on whether WebullBot is performing paper  *
    * trading or live trading.                                              *
    *                                                                       *
    * Updated 03/33/23:                                                     *
    *   - Webull has introduced a new image verification process to verify  *
    *     and approve user logins. This new login feature has limited how   *
    *     MirrorTrader is able to login to user accounts so a workaround    *
    *     login method has been introduced to obtain access. Details on the *
    *     steps that need to be taken in order to login to a Webull account *
    *     can be found here:                                                *
    *                                                                       *
    * https://github.com/tedchou12/webull/wiki/Workaround-for-Login-Method-2
    *                                                                       *
    *                                                                       *
    *   INPUT:                                                              *
    *         device_id (str) - ID of device logging into Webull account.   *
    *                           (Follow URL link above to read steps to get *
    *                            this value).                               *
    *       max_price_diff (float) - The max difference a working order     *
    *                                price can be from an alert price       *
    *                                before it is cancelled.                *
    *           SL_percent (float) - Default stop loss percentage.          *
    *         paper_trading (bool) - Sets paper trading status.             *
    *                 debug (bool) - Sets debug status to view option order *
    *                                details.                               *
    *                   dev (bool) - Sets developer mode status.            *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self, device_id: str="", max_price_diff: float=0.0, SL_percent: float=0.0, 
                paper_trading: bool=False, debug: bool=False, dev: bool=False):        
        self._max_price_diff    = max_price_diff                # Set max order price difference
        self._default_SL        = SL_percent                    # Set default stop loss percent
        self._paper_trading     = paper_trading                 # Set paper trading status flag
        self._debug             = debug                         # Set debug mode status flag
        self._dev               = dev                           # Set developer mode status flag
        self._bot_name          = str(self.__class__.__name__)  # Set bot name

        # Initialize network connection status and logged in status
        self._network_connected = True
        self._logged_in         = False

        # Create stop loss tracker container to manage stop loss orders
        self._stop_loss_tracker = {}

        # If paper trading
        if self._paper_trading:

            logging.info(f"[{self._bot_name}] Executing Paper Trading!")

            # Initialize Webull for paper trading
            self._wb            = paper_webull()
            self._wb.timeout    = glob.WEBULL_TIMEOUT

            # Initialize manage paper orders and stop loss threads
            self._manage_paper_orders_thread    = None
            self._manage_paper_stop_loss_thread = None

            # -- Paper Trading --
            self._paper_account_info    :   dict    =   {       # Paper trading account information
                                                            "ID"                :   0,          # integer
                                                            "Account Type"      :   "PAPER",    # string
                                                            "Market Value"      :   0.0,        # float
                                                            "Cash Balance"      :   0.0,        # float
                                                            "Day P&L"           :   0.0,        # float
                                                            "Total P&L"         :   0.0,        # float
                                                            "Total P&L Percent" :   0.0         # float
                                                        }

            self._active_paper_trades   :   list[dict]  = [{    # Paper trading active trades
                                                                "TradeID"           :   "",     # string
                                                                "Ticker"            :   "",     # string
                                                                "Price"             :   0.0,    # float
                                                                "Quantity"          :   0,      # integer
                                                                "TotalCost"         :   0.0,    # float
                                                                "LastPrice"         :   0.0,    # float
                                                                "ProfitLoss"        :   0.0,    # float
                                                                "ProfitLossPercent" :   0.0,    # float
                                                            }]

            self._active_paper_orders   :   list[dict]  = [{    # Paper trading active orders
                                                                "OrderID"           :   "",     # string
                                                                "Ticker"            :   "",     # string
                                                                "Quantity"          :   0,      # integer
                                                                "LimitPrice"        :   0.0,    # float
                                                                "OrderType"         :   "",     # string
                                                                "Action"            :   "",     # string
                                                                "FullOrder"         :   {}      # dictionary
                                                            }]

            self._working_paper_order   :   dict    =   {       # Paper trading working order
                                                            "Action"            :   "",         # string
                                                            "OrderID"           :   "",         # string
                                                            "Ticker"            :   "",         # string
                                                            "OrderType"         :   "",         # string
                                                            "Filled"            :   False       # bool
                                                        }

        # Else live trading
        else:

            logging.info(f"[{self._bot_name}] Executing Live Trading!")

            # Initialize Webull for live trading
            self._wb            = webull()
            self._wb.timeout    = glob.WEBULL_TIMEOUT

            # Initialize manage orders and stop loss threads
            self._manage_orders_thread      = None
            self._manage_stop_loss_thread   = None

            # -- Live Trading --
            self._account_info          :   dict    =   {       # Live trading account information
                                                            "ID"                :   0,          # integer
                                                            "Account Type"      :   "",         # string
                                                            "Risk"              :   "",         # string
                                                            "Remaining Trades"  :   "",         # string
                                                            "Market Value"      :   0.0,        # float
                                                            "Cash Balance"      :   0.0,        # float
                                                            "Net Value"         :   0.0,        # float
                                                            "Settled Cash"      :   0.0,        # float
                                                            "Unsettled Cash"    :   0.0,        # float
                                                            "Option BP"         :   0.0         # float
                                                        }

            self._active_trades         :   list[dict]  = [{    # Live trading active trades
                                                                "OptionID"          :   "",     # string
                                                                "Ticker"            :   "",     # string
                                                                "StrikePrice"       :   "",     # string
                                                                "Direction"         :   "",     # string
                                                                "ExpDate"           :   None,   # datetime
                                                                "Price"             :   0.0,    # float
                                                                "Quantity"          :   0,      # integer
                                                                "TotalCost"         :   0.0,    # float
                                                                "LastPrice"         :   0.0,    # float
                                                                "ProfitLoss"        :   0.0,    # float
                                                                "ProfitLossPercent" :   0.0,    # float
                                                                "Pointer"           :   0,      # integer
                                                                "TimeStamp"         :   0.0     # float
                                                            }]

            self._active_orders         :   list[dict]  = [{    # Live trading active orders
                                                                "OrderID"           :   "",     # string
                                                                "Ticker"            :   "",     # string
                                                                "Quantity"          :   0,      # integer
                                                                "LimitPrice"        :   0.0,    # float
                                                                "StopLoss"          :   0.0,    # float
                                                                "OrderType"         :   "",     # string
                                                                "Action"            :   "",     # string
                                                                "Pointer"           :   0,      # integer
                                                                "TimeStamp"         :   0.0,    # float
                                                            }]

            self._working_order         :   dict    =   {       # Live trading working order
                                                            "Action"            :   "",         # string
                                                            "OrderID"           :   "",         # string
                                                            "Ticker"            :   "",         # string
                                                            "OptionID"          :   "",         # string
                                                            "StopLoss"          :   0.0,        # float
                                                            "OrderType"         :   "",         # string
                                                            "Filled"            :   False       # bool
                                                        }




        self._wb._set_did(did=device_id)    # Set the device ID

        return



    '''
    =========================================================================
    * login()                                                               *
    =========================================================================
    * This function will use a user's login credentials to log into a       *
    * Webull trading account.                                               *
    *                                                                       *
    *   INPUT:                                                              *
    *          username (str) - Email or phone number for Webull account.   *
    *          password (str) - Password for Webull account.                *
    *         trade_pin (str) - Pin used to view Webull account data.       *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def login(self, username: str="", password: str="", trade_pin: str=""):
        # Initialize and track the number of login attempts made/available
        login_attempts = 0

        # Loop until max number of login attempts have been reached
        while login_attempts < glob.MAX_WEBULL_LOGIN_ATTEMPTS:

            # If no user or password or trade pin provided or invalid login
            if (not username) or (not password) or (not trade_pin) or (login_attempts > 0):
                # Get Webull username, password, and trade pint
                username = input(f"[{self._bot_name}] Enter Webull Username/Phone Number: ")
                password = getpass(f"[{self._bot_name}] Enter Webull Password: ")
                trade_pin = getpass(f"[{self._bot_name}] Enter Webull 6-Digit Trade Pin: ")

            # Login to webull account and get account trade token
            login_results = self._wb.login(username=username, password=password)
            token_received = self._wb.get_trade_token(password=trade_pin)

            # If successful login
            if token_received:

                logging.info(f"[{self._bot_name}] Login Successful!")

                # Set logged in status to true
                self._logged_in = True

                return

            # Else unsuccessful login
            else:
                logging.warning(f"[{self._bot_name}] {login_results['code']} -- {login_results['msg']}")
                login_attempts = glob.MAX_WEBULL_LOGIN_ATTEMPTS - login_results['data']['allowPwdErrorTime']
                logging.warning(f"[{self._bot_name}] ({login_attempts}/{glob.MAX_WEBULL_LOGIN_ATTEMPTS}) login attempts tried.")

        # If maximum login attempts have been reached
        if login_attempts == glob.MAX_WEBULL_LOGIN_ATTEMPTS:
            logging.error(f"[{self._bot_name}] Max number of login attempts have been reached. . . stopping login execution.")

        return



    '''
    =========================================================================
    * logout()                                                              *
    =========================================================================
    * This function will logout of a user's webull trading account.         *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def logout(self):
        # If logged in
        if self._logged_in:

            # If successful logout
            if self._wb.logout() == 200:

                logging.info(f"[{self._bot_name}] Logout successful!")

                # Reset logged in status
                self._logged_in = False

            # Else unsuccessful logout
            else:
                logging.error(f"[{self._bot_name}] Logout unsuccessful!")

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    #########################################################################
    #               D A T A   C O L L E C T   F U N C T I O N S             #
    #########################################################################
    '''
    =========================================================================
    * _get_account_info()                                                   *
    =========================================================================
    * This function will collect information from a user's webull trading   *
    * account (cash available, market value, etc.).                         *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_account_info(self) -> dict:
        try:
            portfolio_info  = self._wb.get_portfolio()      # Get portfolio data
            account_id      = self._wb.get_account_id()     # Get account ID
            account_info    = self._wb.get_account()        # Get account information

        # *** Connection Error ***
        except (requests.exceptions.ConnectionError):
            # TODO: Send error message
            return self._paper_account_info if self._paper_trading else self._account_info

        # If paper trading
        if self._paper_trading:

            # Set paper account ID and account type
            self._paper_account_info["ID"]                  = int(account_id)
            self._paper_account_info["Account Type"]        = "PAPER"

            # Set paper total market value ($ value of all open positions held)
            self._paper_account_info["Market Value"]        = float(portfolio_info["totalMarketValue"])

            # Set paper cash balance ($ value of funds to invest)
            self._paper_account_info["Cash Balance"]        = float(portfolio_info["usableCash"])

            # Set paper profit/loss for the day
            self._paper_account_info["Day P&L"]             = float(portfolio_info["dayProfitLoss"])

            # Set paper total profit/loss ($)
            self._paper_account_info["Total P&L"]           = float(account_info["totalProfitLoss"])

            # Set paper total profit/loss (%)
            self._paper_account_info["Total P&L Percent"]   = round((float(account_info["totalProfitLossRate"]) * 100), 2)

            return self._paper_account_info


        # Else live trading
        else:

            # Set account ID
            self._account_info["ID"]                = int(account_id)

            # Set account type (Cash/Margin)
            self._account_info["Account Type"]      = account_info["accountType"]

            # Set risk status (account risk)
            self._account_info["Risk"]              = portfolio_info["riskStatus"]

            # Set remaining trade times (# of trades that can be made)
            self._account_info["Remaining Trades"]  = portfolio_info["remainTradeTimes"]

            # Set total market value ($ value of all open positions held)
            self._account_info["Market Value"]      = float(portfolio_info["totalMarketValue"])

            # Set cash balance ($ value of settled + unsettled funds)
            self._account_info["Cash Balance"]      = float(portfolio_info["cashBalance"])

            # Set net value ($ value of all assets in trading account)
            self._account_info["Net Value"]         = round((self._account_info["Market Value"] + self._account_info["Cash Balance"]), 2)

            # Set settled funds ($ value of cash available for trades)
            self._account_info["Settled Cash"]      = float(portfolio_info["settledFunds"])

            # Set unsettled funds ($ value of cash unavailable for trades)
            self._account_info["Unsettled Cash"]    = float(portfolio_info["unsettledFunds"])

            # Set option buying power ($ value of cash available to use for options trading)
            self._account_info["Option BP"]         = float(portfolio_info["optionBuyingPower"])

            return self._account_info



    '''
    =========================================================================
    * _get_active_trades()                                                  *
    =========================================================================
    * This function will iterate through a user's active trades and build a *
    * active trades table for the webull trading bot to reference. The      *
    * table will only contain active option trades.                         *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_active_trades(self) -> list[dict]:
        try:
            current_positions   = self._wb.get_positions()                                      # Get latest trade positions
        
        # *** Key / Connection Error ***
        except (KeyError,requests.exceptions.ConnectionError):
            # TODO: Send error message
            # logging.error(f"[{self._bot_name}] Unable to get the latest trade positions!")
            # logging.error(f"[{self._bot_name}] ACCOUNT DATA COLLECTED: {self._wb.get_account()}")
            return self._active_paper_trades if self._paper_trading else self._active_trades

        # If live trading
        if not self._paper_trading:
            duplicate_trades    = set()                                                         # Initialize duplicate trades set
            pointer_idx         = 1                                                             # Initialize pointer index to active orders table for ticker
            self._active_trades.clear()                                                         # Reset active trades table
        
        # Else paper trading
        else:
            self._active_paper_trades.clear()                                                   # Reset active paper trades table

        # Iterate through all active positions
        for position in current_positions:
            entry = {}                                                                          # Initialize active trades entry

            # If paper trading
            if self._paper_trading:
                entry["TradeID"]            = position['id']                                    # Set trade ID
                entry["Ticker"]             = position['ticker']['symbol']                      # Set ticker symbol
                entry["Price"]              = float(position['costPrice'])                      # Set price per share
                entry["Quantity"]           = int(position['position'])                         # Set number of shares held
                entry["TotalCost"]          = float(position['cost'])                           # Set the total cost for the active paper position
                entry["LastPrice"]          = float(position['lastPrice'])                      # Set the last price for the active paper position
                entry["ProfitLoss"]         = float(position['unrealizedProfitLoss'])           # Set the profit/loss dollar amount
                entry["ProfitLossPercent"]  = float(position['unrealizedProfitLossRate'])       # Set the profit/loss percentage

                self._active_paper_trades.append(entry)                                         # Add entry to active paper trades table

            # Else if live trading AND current active position is an option trade
            elif (not self._paper_trading) and (str(position['assetType']).upper() == "OPTION"):
                entry["OptionID"]           = position['tickerId']                              # Set option trade ID
                entry["Ticker"]             = position['ticker']['symbol']                      # Set ticker symbol
                
                try:
                    # Get option quote for current option trade
                    opt_quote               = self._wb.get_option_quote(stock=entry["Ticker"],optionId=entry["OptionID"])
                    entry["StrikePrice"]    = opt_quote['data'][0]['strikePrice']               # Set option contract strike price
                    entry["Direction"]      = opt_quote['data'][0]['direction']                 # Set option contract direction (call/put)
                    entry["ExpDate"]        = parse(opt_quote['data'][0]['expireDate']).date()  # Set option contract expiration date
                
                # *** Connection Error ***
                except (requests.exceptions.ConnectionError):
                    # TODO: Send error message
                    entry["StrikePrice"]    = 'N/A'                                             # Set invalid option contract strike price
                    entry["Direction"]      = 'N/A'                                             # Set invalid option contract direction (call/put)
                    entry["ExpDate"]        = None                                              # Set invalid option contract expiration date
                
                entry["Price"]              = float(position['costPrice'])                      # Set the price per option contract
                entry["Quantity"]           = int(position['position'])                         # Set the number of contracts held
                entry["TotalCost"]          = float(position['cost'])                           # Set the total cost for all contracts purchased
                entry["LastPrice"]          = float(position['lastPrice'])                      # Set the last price for the active positions
                entry["ProfitLoss"]         = float(position['unrealizedProfitLoss'])           # Set the profit/loss dollar amount
                entry["ProfitLossPercent"]  = float(position['unrealizedProfitLossRate'])       # Set the profit/loss percentage
                entry["Pointer"]            = 1                                                 # Set pointer to active orders table for ticker
                entry["TimeStamp"]          = float(position['updatePositionTimeStamp'])        # Set the position timestamp
                
                # If multiple option contract for the same ticker have been found
                if entry["Ticker"] in duplicate_trades:
                    pointer_idx             += 1                                                # Increment pointer index to active orders table for ticker
                    entry["Pointer"]        = pointer_idx                                       # Set pointer to active orders table for ticker
                
                duplicate_trades.add(entry["Ticker"])                                           # Add ticker to duplicate trades set

                self._active_trades.append(entry)                                               # Add entry to active trades table

        return self._active_paper_trades if self._paper_trading else self._active_trades



    '''
    =========================================================================
    * _get_active_orders()                                                  *
    =========================================================================
    * This function will iterate through a user's active orders and build a *
    * active orders table for the webull trading bot to reference. The      *
    * table will only contain active orders that are option trade orders.   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_active_orders(self) -> list[dict]:
        # Get latest trade orders
        try:
            current_orders = self._wb.get_current_orders()                                      # Get latest trade orders

        # *** Key / Connection Error ***
        except (KeyError,requests.exceptions.ConnectionError):
            # TODO: Send error message
            # logging.error(f"[{self._bot_name}] Unable to get the latest trade orders!")
            # logging.error(f"[{self._bot_name}] ACCOUNT DATA COLLECTED: {self._wb.get_account()}")
            # return self._active_paper_orders if self._paper_trading else (self._active_trades, self._active_orders)
            return self._active_paper_orders if self._paper_trading else self._active_orders

         # If live trading
        if not self._paper_trading:
            self._active_orders.clear()                                                         # Reset active orders table
        
        # Else paper trading
        else:
            self._active_paper_orders.clear()                                                   # Reset active paper orders table

        # Iterate through all active orders
        for order in current_orders:
            entry = {}                                                                          # Initialize active orders entry

            # If paper trading
            if self._paper_trading:
                entry["OrderID"]            = order['orderId']                                  # Set order ID
                entry["Ticker"]             = order['ticker']['symbol']                         # Set ticker symbol
                entry["Quantity"]           = int(order['totalQuantity'])                       # Set number of shares to buy/sell
                entry["LimitPrice"]         = 0.0                                               # Initialize the order limit price (MARKET ORDERS ONLY)
                entry["OrderType"]          = order['orderType']                                # Set order type (LIMIT / MARKET)
                entry["Action"]             = order['action']                                   # Set the action to perform (BUY / SELL)
                
                # If the active order is "LIMIT" (Buy/Sell Orders)
                if entry["OrderType"] == "LMT":
                    entry["LimitPrice"]     = float(order['lmtPrice'])                          # Set the order limit price (LIMIT ORDERS ONLY)
                
                entry["FullOrder"]          = order                                             # Set the full order dictionary

                self._active_paper_orders.append(entry)                                         # Add entry to active paper trades table

            # Else if live trading AND current active order is an option order
            elif (not self._paper_trading) and (str(order['assetType']).upper() == "OPTION"):
                entry["OrderID"]            = order['orderId']                                  # Set order ID
                entry["Ticker"]             = order['ticker']['symbol']                         # Set ticker symbol
                entry["Quantity"]           = int(order['totalQuantity'])                       # Set number of contracts to buy/sell
                entry["LimitPrice"]         = 0.0                                               # Initialize the order limit price
                entry["StopLoss"]           = 0.0                                               # Initialize the order stop loss price
                entry["OrderType"]          = order['orderType']                                # Set order type (LIMIT / MARKET / STOP)
                entry["Action"]             = order['action']                                   # Set the action to perform (BUY / SELL)
                entry["Pointer"]            = 0                                                 # Initialize pointer to active trades table
                entry["TimeStamp"]          = float(order['createTime0'])                       # Set the order timestamp

                # If active order is "STOP" (Stop Loss Orders)
                if entry["OrderType"] == "STP":
                    entry["StopLoss"]       = float(order['auxPrice'])                          # Set order stop loss price

                # Else if active order is "LIMIT" (Buy / Sell Orders)
                elif entry["OrderType"] == "LMT":
                    entry["LimitPrice"]     = float(order['lmtPrice'])                          # Set order limit price

                self._active_orders.append(entry)                                               # Add entry to active orders table

        # If live trading AND there are active trades
        if (not self._paper_trading) and (self._active_trades):

            # Iterate through table orders to map order entry pointers to trade entry pointers
            for order in self._active_orders:
                # If current order is "STOP" (Stop Loss Order)
                if order["OrderType"] == "STP":
                    # Find timestamp in active trades table that closely matches to the current order timestamp
                    closest_trade_match = min(self._active_trades, key=lambda position: abs(position["TimeStamp"] - order["TimeStamp"]))
                    order["Pointer"]    = closest_trade_match["Pointer"]


        return self._active_paper_orders if self._paper_trading else self._active_orders



    #########################################################################
    #               P L A C E   O R D E R   F U N C T I O N S               #
    #########################################################################
    '''
    =========================================================================
    * place_order()                                                         *
    =========================================================================
    * This function will place a buy or sell order for a specific option    *
    * trade.                                                                *
    *                                                                       *
    *   INPUT:                                                              *
    *                 action (str) - Buy or Sell.                           *
    *                 ticker (str) - Stock symbol.                          *
    *           strike_price (str) - Expected price the stock will reach.   *
    *              direction (str) - Call (Bullish) or Put (Bearish).       *
    *          exp_date (datetime) - Expiration date of option contract.    *
    *                price (float) - Price per option contract.             *
    *              percent (float) - Percent of cash to invest.             *
    *            stop_loss (float) - Stop loss price per option contract.   *
    *             order_type (str) - 'MKT' or 'LMT' order.                  *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def place_order(self, action="", ticker="", strike_price="", direction="", exp_date=None, price=0.0, percent=0.0, stop_loss=0.0, order_type="LMT"):

        # If action is not BUY or SELL
        if (not action) or (action.upper() not in ["BUY", "SELL"]):
            logging.error(f"[{self._bot_name}] Need to specify a BUY or SELL action in order to place a options order!")
            return

        # If SELL action
        if action.upper() == "SELL":

            # Find and cancel stop loss order
            self.cancel_stop_loss_order(ticker=ticker,
                                        strike=strike_price, 
                                        direction=direction, 
                                        exp_date=exp_date)

        # Get the ID for the option trade
        id_found, option_id, exp_date = self.get_option_trade_id(ticker=ticker, 
                                                                 strike_price=strike_price, 
                                                                 direction=direction, 
                                                                 exp_date=exp_date)

        # If option contract ID found
        if id_found:

            # Don't place BUY order if same day expiration and time is after 12pm PST
            # otherwise exchange (Webull) will reject the order
            if (action == "BUY") and (exp_date == dt.date.today()) and (dt.datetime.now().time() > dt.time(12,0,0)):
                logging.error(f"[{self._bot_name}] Opening positions is not allowed after 12PM PST on the option expiration date!")
                return


            # Get the current price of the option contract (non paper trading) or stock ticker (paper trading)
            quote_price, use_market_price = self.get_stock_quote(ticker=ticker,
                                                                 option_id=option_id)

            # If 'Bid'/'Ask' spread is small
            if use_market_price:
                order_type = "MKT"  # Update order type to MKT order

            # If BUY action and no alert price provided or the quote price is less than the alert price OR
            # SELL action and no alert price provided or the quote price is greater than the alert price
            if ((action.upper() == "BUY") and ((price == 0.0) or (quote_price < price))) or \
               ((action.upper() == "SELL") and ((price == 0.0) or (quote_price > price))):

                # If stop loss price greater than price of option contract
                if stop_loss >= quote_price:
                    stop_loss_percent = (price - stop_loss) / price             # Determine stop loss percentage
                    stop_loss = quote_price - (quote_price * stop_loss_percent) # Set new stop loss price

                # Set the alert price to be the quote price
                price = quote_price


            # Adjust price and stop loss price by increments of 0.05 if price is between 0.0 and 3.00 
            # otherwise exchange (Webull) will reject the order
            if price > 0.0 and price < 3.0:
                price = round(round(price / glob.PRICE_INCREMENT) * glob.PRICE_INCREMENT, 2)

            if stop_loss > 0.0 and stop_loss < 3.0:
                stop_loss = round(round(stop_loss / glob.PRICE_INCREMENT) * glob.PRICE_INCREMENT, 2)


            # If BUY action
            if action.upper() == "BUY":

                # Get the number of contracts or shares to buy
                quantity = self.get_quantity_buy(price=price, 
                                                 percentage=percent)

            # Else if SELL action
            elif action.upper() == "SELL":

                # Get the number of contracts or shares to sell
                quantity = self.get_quantity_sell(ticker=ticker,
                                                  option_id=option_id, 
                                                  percentage=percent)


            # If quantity and price valid
            if (quantity > 0) and (price > 0.0):

                logging.info(f"[{self._bot_name}] Placing {action} order for {quantity} contract(s) of {ticker} @{price}!")

                # If market open and developer mode not enabled
                if (glob.MARKET_OPEN.is_set()) and (not self._dev):

                    # Place a limit or market 'BUY or 'SELL' order for the option contract
                    status = self.place_options_order(action=action, 
                                                      option_id=option_id, 
                                                      limit_price=price, 
                                                      quantity=quantity, 
                                                      order_type=order_type, 
                                                      enforce="DAY")

                    # If successful BUY/SELL order placed
                    if (status) and ('orderId' in status):

                        logging.info(f"[{self._bot_name}] Successfully placed option {action} order for {ticker}!")

                        # Add order to working orders queue
                        self._working_order["Action"] = action
                        self._working_order["OrderID"] = status['orderId']
                        self._working_order["Ticker"] = ticker
                        self._working_order["OptionID"] = option_id
                        self._working_order["StopLoss"] = stop_loss
                        self._working_order["OrderType"] = order_type
                        self._working_order["Filled"] = False
                        glob.WORKING_ORDERS_QUEUE.put(self._working_order)

                    # Else BUY/SELL order not placed
                    else:

                        # If status available
                        if status:
                            if self._debug:
                                logging.info(f"[{self._bot_name}] ===> STATUS MESSAGE: {status}")
                            logging.error(f"[{self._bot_name}] ERROR: {status['msg']}")
                            logging.error(f"[{self._bot_name}] Unable to place {action} order for {ticker}!")

                        # Else status is not available
                        else:
                            logging.error(f"[{self._bot_name}] No status available for option {action} order for {ticker}!")

            # Else quantity or price are not valid
            else:

                # If BUY action
                if action.upper() == "BUY":
                    logging.warning(f"[{self._bot_name}] Insufficient funds to purchase contracts of {ticker} @{price}!")

                # If SELL action
                if action.upper() == "SELL":
                    logging.warning(f"[{self._bot_name}] Insufficient quantity of {ticker} contracts to sell!")


        # Else option contract ID not found
        else:
            logging.error(f"[{self._bot_name}] No option contract ID found for [{ticker} | {strike_price} | {direction} | {exp_date}]!")

        return



    '''
    =========================================================================
    * place_options_order()                                                 *
    =========================================================================
    * This function will place an options buy or sell order.                *
    *                                                                       *
    *   INPUT:                                                              *
    *              action (str) - Buy or Sell option contract.              *
    *           option_id (str) - The associated ID of the option trade.    *
    *         limit_price (str) - The price to buy/sell a option contract.  *
    *          stop_price (str) - The price to stop at per option contract. *
    *            quantity (str) - The number of option contracts being      *
    *                             bought or sold.                           *
    *          order_type (str) - The type of order being placed            *
    *                             (see comments below).                     *
    *             enforce (str) - Determines when an order should be        *
    *                             canceled (see comments below).            *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def place_options_order(self, action="", option_id="", limit_price=0.0, stop_price=0.0, quantity=0, order_type='LMT', enforce='DAY'):
        # ===============================================================================================================================
        # Available order_types:                                                                                                        #
        #   1.) Limit       (LMT):      Buy/Sell at a fixed price or lower.                                                             #
        #                                                                                                                               #
        #   2.) Market      (MKT):      Buy/Sell at market price.                                                                       #
        #                                                                                                                               #
        #   3.) Stop        (STP):      Set a stop price higher than the current price. If market price rises above the stop price, a   #
        #                               market BUY order is triggered.                                                                  #
        #                                                                                                                               #
        #   4.) Stop Limit  (STP LMT):  Set a stop price higher than the current price. If the latest price rises to the stop price, a  #
        #                               limit BUY order is triggered.                                                                   #
        #                                                                                                                               #
        # Available enforce:                                                                                                            #
        #   1.) DAY:                        The order will be canceled after the market closes on the day.                              #
        #                                                                                                                               #
        #   2.) GTC (Good 'Till Canceled):  If the order has not been filled, it will be canceled up to 60 natural days after the order #
        #                                   is placed.                                                                                  #
        # ===============================================================================================================================

        # Initialize status to empty dictionary
        status = {}

        logging.info(f"[{self._bot_name}] Placing {order_type} {action} order @ [LMT: {limit_price} | STP: {stop_price}] for {quantity} contract(s). . .")

        try:

            # Place option contract order and get status
            status = self._wb.place_order_option(optionId=option_id, 
                                                 lmtPrice=limit_price, 
                                                 stpPrice=stop_price,
                                                 action=action, 
                                                 orderType=order_type, 
                                                 enforce=enforce, 
                                                 quant=quantity)

        # *** Type Error ***
        except TypeError:
            logging.error(f"[{self._bot_name}] Type error occurred. . . Unable to place option order!", exc_info=True)

        # *** Unknown Error ***
        except Exception as e:
            logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

        return status



    '''
    =========================================================================
    * place_stop_loss_order()                                               *
    =========================================================================
    * This function will place a stop loss sell order on an options trade.  *
    * Note: This function is specifically used for live-trading only.       *
    *                                                                       *
    *   INPUT:                                                              *
    *               ticker (str) - The stock ticker symbol.                 *
    *            option_id (str) - The associated id of an options trade.   *
    *       filled_price (float) - The price the trade was filled at.       *
    *         stop_price (float) - The stop price for the sell order.       *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def place_stop_loss_order(self, ticker="", option_id="", filled_price=0.0, stop_price=0.0):

        # If no stop price provided
        if not stop_price:

            # Get the current price of the option contract
            price, use_market_price = self.get_stock_quote(ticker=ticker,
                                                           option_id=option_id)
 
            # If valid price
            if price > 0.0:

                # Set a default stop loss price
                stop_price = round((price - (price * self._default_SL)), 2)

                # If debugging enabled
                if self._debug:
                    logging.info(f"[{self._bot_name}] (DEBUG) [Option ID: {option_id} | Price: {price}] ==> Stop Price: {stop_price}")

            # Else invalid price
            else:
                logging.error(f"[{self._bot_name}] Unable to obtain a valid stop loss price!")
                stop_price = 0.0


        # If stop loss price greater than price of option contract
        if stop_price >= filled_price:
            # Set new stop loss price using default stop loss percentage
            stop_price = filled_price - (filled_price * self._default_SL)


        # Adjust stop loss price by increments of 0.05 if price is between 0.0 and 3.00 
        # otherwise exchange (Webull) will reject the order
        if stop_price > 0.0 and stop_price < 3.0:
            stop_price = round(round(stop_price / glob.PRICE_INCREMENT) * glob.PRICE_INCREMENT, 2)


        # Get 100% of contracts held for option id
        quantity = self.get_quantity_sell(option_id=option_id, 
                                          percentage=1.0)


        # If valid stop price and quantity
        if (stop_price > 0.0) and (quantity > 0):

            # Place STOP SELL order for all contracts held
            status = self.place_options_order(action="SELL", 
                                              option_id=option_id, 
                                              stop_price=stop_price, 
                                              quantity=quantity, 
                                              order_type="STP", 
                                              enforce="GTC")

            # If successful stop order placed
            if (status) and ('orderId' in status):

                logging.info(f"[{self._bot_name}] Successfully placed option STOP LOSS order!")

            # Else stop order not placed
            else:

                # If status available
                if status:
                    if self._debug:
                        logging.info(f"[{self._bot_name}] ===> STATUS MESSAGE: {status}")

                    logging.error(f"[{self._bot_name}] ERROR: {status['msg']}")

                # Else status is not available
                else:
                    logging.error(f"[{self._bot_name}] No stop loss order status available!")
                
                logging.error(f"[{self._bot_name}] Unable to place option STOP LOSS order!")


        # Else invalid stop price or quantity
        else:

            # If invalid stop price
            if stop_price == 0.0:
                logging.warning(f"[{self._bot_name}] Can't place stop loss order with invalid stop loss price!")

            # If invalid quantity
            if quantity == 0:
                logging.warning(f"[{self._bot_name}] Can't place stop loss order with insufficient quantity!")

        return



    '''
    =========================================================================
    * place_paper_order()                                                   *
    =========================================================================
    * This function will place a paper buy or sell order.                   *
    *                                                                       *
    *   INPUT:                                                              *
    *            action (str) - Buy or Sell.                                *
    *            ticker (str) - The stock symbol of the trade.              *
    *         percent (float) - Percentage of available cash to invest.     *
    *            short (bool) - Determine if shorting a stock.              *
    *        order_type (str) - 'MKT' or 'LMT' order.                       *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def place_paper_order(self, action="", ticker="", percent=0.0, short=False, order_type="LMT"):

        # If no BUY or SELL action is provided
        if (not action) or (action.upper() not in ["BUY", "SELL"]):
            logging.warning(f"[{self._bot_name}] Need to specify a BUY or SELL action in order to place a options order!")
            return

        # Get the current price of the option contract (live trading) or stock ticker (paper trading)
        price, use_market_price = self.get_stock_quote(ticker=ticker)

        # If 'Bid'/'Ask' spread is small
        if use_market_price:
            order_type = "MKT"      # Update order type to MKT order

        # If BUY action
        if action.upper() == "BUY":

            # If shorting stock (equivalent to PUT direction)
            if short:

                # Get the number of shares to buy back
                quantity = self.get_quantity_sell(ticker=ticker, percentage=percent)

            # Else not shorting stock (equivalent to CALL direction)
            else:

                # Get the number of shares to buy
                quantity = self.get_quantity_buy(percentage=percent, price=price)

        # If SELL action
        elif action.upper() == "SELL":

            # If shorting stock (equivalent to PUT direction)
            if short:

                # Get the number of shares to short
                quantity = self.get_quantity_buy(percentage=percent, price=price)

            # Else not shorting stock (equivalent to CALL direction)
            else:

                # Get the number of shares to sell
                quantity = self.get_quantity_sell(ticker=ticker, percentage=percent)


        # If quantity and price valid
        if (quantity > 0) and (price > 0.0):

            logging.info(f"[{self._bot_name}] Placing paper {action} order for {quantity} share(s) of {ticker} @{price}!")

            # If market open and developer mode not enabled
            if (glob.MARKET_OPEN.is_set()) and (not self._dev):

                # Place a limit 'BUY or 'SELL' order for the stock
                status = self._wb.place_order(stock=ticker, 
                                              price=price, 
                                              quant=quantity, 
                                              action=action, 
                                              orderType=order_type, 
                                              enforce='DAY')

                # If successful BUY/SELL paper order placed
                if (status) and ('orderId' in status):

                    logging.info(f"[{self._bot_name}] Successfully placed paper {action} order for {ticker}!")

                    # Add paper order to working orders queue
                    self._working_paper_order["Action"] = action
                    self._working_paper_order["OrderID"] = status['orderId']
                    self._working_paper_order["Ticker"] = ticker
                    self._working_paper_order["OrderType"] = order_type
                    self._working_paper_order["Filled"] = False
                    glob.WORKING_ORDERS_QUEUE.put(self._working_paper_order)

                # Else BUY/SELL paper order not placed
                else:

                    # If status available
                    if status is not None:
                        logging.error(f"[{self._bot_name}] ERROR: {status['msg']}")
                        logging.error(f"[{self._bot_name}] Unable to place {action} order for {ticker}!")

                    # Else status is not available
                    else:
                        logging.error(f"[{self._bot_name}] No status available!")

        # Else quantity or price are not valid
        else:

            # If invalid quantity value
            if quantity == 0:

                # If BUY action
                if action.upper() == "BUY":

                    # If shorting stock (equivalent to PUT direction)
                    if short:
                        logging.warning(f"[{self._bot_name}] Insufficient quantity of {ticker} shares to buy back!")

                    # Else not shorting stock (equivalent to CALL direction)
                    else:
                        logging.warning(f"[{self._bot_name}] Insufficient funds to buy shares of {ticker} using {percent*100}% of account value!")

                # If SELL action
                if action.upper() == "SELL":

                    # If shorting stock (equivalent to PUT direction)
                    if short:
                        logging.warning(f"[{self._bot_name}] Insufficient funds to short shares of {ticker} using {percent*100}% of account value!")

                    # Else not shorting stock (equivalent to CALL direction)
                    else:
                        logging.warning(f"[{self._bot_name}] Insufficient quantity of {ticker} shares to sell!")

            # If invalid price value
            if price == 0.0:
                logging.warning(f"[{self._bot_name}] Cannot place paper order for {ticker} because it could not be found!")

        return



    #########################################################################
    #                   T H R E A D   F U N C T I O N S                     #
    #########################################################################
    '''
    =========================================================================
    * run_manager_threads()                                                 *
    =========================================================================
    * This function will start threads that will manage active orders and   *
    * stop loss prices for option trades.                                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def run_manager_threads(self):

        # If paper trading
        if self._paper_trading:

            # Initialize thread to manage paper orders
            self._manage_paper_orders_thread = threading.Thread(target=self.manage_active_paper_orders) # Initialize thread
            self._manage_paper_orders_thread.setName(name="Manage Paper Orders")                        # Set name of thread
            self._manage_paper_orders_thread.setDaemon(daemonic=True)                                   # Set thread as background task

            # Start manage paper orders thread and add to active threads list
            self._manage_paper_orders_thread.start()
            glob.ACTIVE_THREADS.append(self._manage_paper_orders_thread)

            # # Initialize thread to manage paper stop losses
            # self._manage_paper_stop_loss_thread = threading.Thread(target=self.manage_paper_stop_loss)  # Initialize thread
            # self._manage_paper_stop_loss_thread.setName(name="Manage Paper Stop Loss")                  # Set name of thread
            # self._manage_paper_stop_loss_thread.setDaemon(daemonic=True)                                # Set thread as background task

            # # Start manage paper stop losses thread and add to active threads list
            # self._manage_paper_stop_loss_thread.start()
            # glob.ACTIVE_THREADS.append(self._manage_paper_stop_loss_thread)

        # Else live trading
        else:

            # Initialize thread to manage active orders
            self._manage_orders_thread = threading.Thread(target=self.manage_active_orders)             # Initialize thread
            self._manage_orders_thread.setName(name="Manage Active Orders")                             # Set name of thread
            self._manage_orders_thread.setDaemon(daemonic=True)                                         # Set thread as background task

            # Start manage orders thread and add to active threads list
            self._manage_orders_thread.start()
            glob.ACTIVE_THREADS.append(self._manage_orders_thread)


        # Initialize thread to manage stop losses
        self._manage_stop_loss_thread = threading.Thread(target=self.manage_stop_loss)              # Initialize thread
        self._manage_stop_loss_thread.setName(name="Manage Stop Loss")                              # Set name of thread
        self._manage_stop_loss_thread.setDaemon(daemonic=True)                                      # Set thread as background task

        # Start manage stop losses thread and add to active threads list
        self._manage_stop_loss_thread.start()
        glob.ACTIVE_THREADS.append(self._manage_stop_loss_thread)
        return



    '''
    =========================================================================
    * manage_active_orders()                                                *
    =========================================================================
    * This function will manage active buy/sell orders to ensure that they  *
    * get filled.                                                           *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def manage_active_orders(self):

        try:
            # Loop while market open and network connection is established
            while (glob.MARKET_OPEN.is_set()) and (self._network_connected):
                
                try:
                    # If working orders queue is not empty
                    if not glob.WORKING_ORDERS_QUEUE.empty():

                        # Get the working order from the queue
                        order = glob.WORKING_ORDERS_QUEUE.get()

                        # If debugging enabled
                        if self._debug:
                            logging.info(f"[{self._bot_name}] (DEBUG) Working Order Queue Item:\n" +
                                            f"ACTION: {order['Action']}\n" +
                                            f"ORDER ID: {order['OrderID']}\n" +
                                            f"TICKER: {order['Ticker']}\n" +
                                            f"OPTION ID: {order['OptionID']}\n" +
                                            f"STOP LOSS: {order['StopLoss']}\n" +
                                            f"ORDER TYPE: {order['OrderType']}\n")

                        # Initialize the maximum number of attempts that will be made to fill a failed modified order
                        failed_modify_attempts = glob.MAX_FAILED_ORDER_MODIFY_ATTEMPTS

                        # Initialize timer for modifying a LMT order to a MKT order 
                        modify_timer = time.time()

                        # Initialize order cancelled status
                        is_cancelled = False
 
                        # While order has not been filled and network connection is established and market open
                        while (not order["Filled"]) and (self._network_connected) and (glob.MARKET_OPEN.is_set()):

                            # Get current active orders
                            found, active_orders = self.wait_for_order_in_table(orderId=order['OrderID'])
                            
                            # If order in active orders table (order not filled) and order type is not MKT (ALL OUT sell signal)
                            if (found) and (order['OrderID'] in active_orders['OrderID']) and (order['OrderType'] != "MKT"):

                                # Get the order index
                                order_idx = active_orders['OrderID'].index(order['OrderID'])

                                # Get a new order price
                                new_price, use_market_price = self.get_stock_quote(ticker=order['Ticker'], 
                                                                                   option_id=order['OptionID'])

                                # If BUY action and difference between new and current order price is more than max price difference
                                if (order['Action'] == 'BUY') and \
                                   (((new_price - active_orders['LimitPrice'][order_idx]) * 100) > self._max_price_diff):

                                    # Cancel order (Don't chase trade)
                                    logging.warning(f"[{self._bot_name}] Price difference exceeds order price limit! Canceling {order['Action']} order for {order['Ticker']}!")
                                    is_cancelled = self.cancel_order(order_id=order["OrderID"],
                                                                     order_type=active_orders['OrderType'][order_idx])

                                # Else difference between new and current order price is less than or equal to max price difference
                                else:

                                    # If BUY action and limit order and more than <MODIFY_LIMIT_ORDER_TIMEOUT> seconds has passed
                                    if ((order['Action'] == 'BUY') and (active_orders['OrderType'][order_idx] == "LMT") and \
                                       ((time.time() - modify_timer) >= glob.MODIFY_LIMIT_ORDER_TIMEOUT)) or (use_market_price):
                                        
                                        # Update order type to MKT order
                                        active_orders['OrderType'][order_idx] = "MKT"
                                        order['OrderType'] = "MKT"
                                    

                                    # Modify the order with a new price
                                    is_modified = self._wb.modify_order(order_id=order["OrderID"], 
                                                                        stock=active_orders['Ticker'][order_idx], 
                                                                        price=new_price, 
                                                                        action=active_orders['Action'][order_idx],
                                                                        orderType=active_orders['OrderType'][order_idx], 
                                                                        enforce='DAY', 
                                                                        quant=active_orders['Quantity'][order_idx])

                                    # If modified order successfully processed
                                    if is_modified:
                                        logging.info(f"[{self._bot_name}] Successfully modified {active_orders['Action'][order_idx]} order #{order['OrderID']} for {active_orders['Ticker'][order_idx]}!")

                                    # Else modified order not processed
                                    else:
                                        logging.error(f"[{self._bot_name}] Unable to modify {active_orders['Action'][order_idx]} order #{order['OrderID']} for {active_orders['Ticker'][order_idx]}!")

                                        # Decrement the number of modify attempts remaining
                                        failed_modify_attempts -= 1

                                        # If maximum attempts have been reached
                                        if failed_modify_attempts == 0:

                                            # Cancel order
                                            is_cancelled = self.cancel_order(order_id=order["OrderID"], 
                                                                             order_type=active_orders['OrderType'][order_idx])


                            # Else if order not in active orders table
                            elif (not found) or (order['OrderID'] not in active_orders['OrderID']):

                                # Order has been filled or cancelled
                                order['Filled'] = True



                        # If order has not been cancelled and network connection established and market open
                        if (not is_cancelled) and (self._network_connected) and (glob.MARKET_OPEN.is_set()):

                            logging.info(f"[{self._bot_name}] {order['Action']} order #{order['OrderID']} for {order['Ticker']} has been filled!")

                            # Wait until trade table has been updated with the filled order
                            found, active_trades = self.wait_for_trade_in_table(id=order['OptionID'])

                            if self._debug:
                                if found:
                                    logging.info(f"[{self._bot_name}] (DEBUG) OptionID for {order['Ticker']} found in active trades table!")
                                else:
                                    logging.warning(f"[{self._bot_name}] (DEBUG) OptionID for {order['Ticker']} not found in active trades table!")

                            # If BUY order has been filled
                            if (found) and (order['Action'].upper() == "BUY"):

                                # Place Stop Loss order
                                trade_idx = active_trades['OptionID'].index(order['OptionID'])
                                self.place_stop_loss_order(option_id=order['OptionID'],
                                                           filled_price=active_trades['Price'][trade_idx], 
                                                           stop_price=order['StopLoss'])

                            # Else if SELL order has been filled
                            elif (found) and (order['Action'].upper() == "SELL"):

                                # Get the new quantity of contracts held
                                contracts_held = self.get_quantity_sell(option_id=order['OptionID'], 
                                                                        percentage=1.0)

                                # If there are still contracts being held
                                if contracts_held > 0:

                                    # Place new Stop Loss order
                                    trade_idx = active_trades['OptionID'].index(order['OptionID'])
                                    self.place_stop_loss_order(option_id=order['OptionID'], 
                                                               filled_price=active_trades['Price'][trade_idx], 
                                                               stop_price=order['StopLoss'])

                        # If market closed
                        if dt.datetime.now().time() >= glob.MARKET_CLOSE_TIME:

                            # Cancel order
                            is_cancelled = self.cancel_order(order_id=order['OrderID'], 
                                                             order_type=order['OrderType'])

                        # Mark working order queue task as complete
                        glob.WORKING_ORDERS_QUEUE.task_done()

                # *** Connection Error ***
                except requests.exceptions.ConnectionError as e:
                    # Verify internet connection
                    self._network_connected = misc.is_network_connected()

                    # If no internet connection established
                    if not self._network_connected:
                        
                        # Wait for connection to re-establish
                        self._network_connected = misc.wait_for_network_connection()

                    # Else internet connection established
                    else:
                        logging.warning(f"[{self._bot_name}] Internet connection established!. . . CONNECTION ERROR: {e}")

                # *** Unknown Error ***
                except Exception:
                    logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

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

        logging.info(f"[{self._bot_name}] Successfully exited thread: {self._manage_orders_thread.getName()}")

        return



    '''
    =========================================================================
    * manage_active_paper_orders()                                          *
    =========================================================================
    * This function will manage active buy/sell paper orders to ensure that *
    * they get filled.                                                      *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def manage_active_paper_orders(self):

        try:
            # Loop while market open and network connection is established
            while (glob.MARKET_OPEN.is_set()) and (self._network_connected):

                try:
                    # If working orders queue is not empty
                    if not glob.WORKING_ORDERS_QUEUE.empty():

                        # Get the working order from the queue
                        order = glob.WORKING_ORDERS_QUEUE.get()

                        # If debugging enabled
                        if self._debug:
                            logging.info(f"[{self._bot_name}] (DEBUG) Working Paper Order Queue Item:\n" +
                                        f"ACTION: {order['Action']}\n" +
                                        f"ORDER ID: {order['OrderID']}\n" +
                                        f"TICKER: {order['Ticker']}\n" +
                                        f"ORDER TYPE: {order['OrderType']}\n")

                        # Initialize the maximum number of attempts that will be made to fill a failed modified order
                        failed_modify_attempts = glob.MAX_FAILED_ORDER_MODIFY_ATTEMPTS

                        # Initialize timer for modifying a LMT order to a MKT order 
                        modify_timer = time.time()

                        # Initialize order cancelled status
                        is_cancelled = False

                        # While order has not been filled and network connection is established and market open
                        while (not order["Filled"]) and (self._network_connected) and (glob.MARKET_OPEN.is_set()):

                            # Get current active orders
                            found, active_orders = self.wait_for_order_in_table(orderId=order['OrderID'])

                            # If order in active paper orders table (order not filled) and order type is not MKT (ALL OUT sell signal)
                            if (found) and (order['OrderID'] in active_orders['OrderID']) and (order['OrderType'] != "MKT"):

                                # Get the order index
                                order_idx = active_orders['OrderID'].index(order['OrderID'])

                                # Get a new order price
                                new_price, use_market_price = self.get_stock_quote(ticker=active_orders['Ticker'][order_idx])

                                # If BUY action and difference between new and current order price is more than max price difference
                                if (order['Action'] == 'BUY') and \
                                ((new_price - active_orders['LimitPrice'][order_idx]) > self._max_price_diff):

                                    # Cancel BUY order (Don't chase trade)
                                    logging.warning(f"[{self._bot_name}] Price difference exceeds order price limit! Canceling {order['Action']} order for {order['Ticker']}!")
                                    is_cancelled = self.cancel_order(order_id=order["OrderID"], 
                                                                    order_type=active_orders['OrderType'][order_idx])

                                # Else difference between new and current order price is less than or equal to max price difference
                                else:

                                    # If BUY action and more than <MODIFY_LIMIT_ORDER_TIMEOUT> seconds has passed
                                    if ((order['Action'] == 'BUY') and (active_orders['OrderType'][order_idx] == "LMT") and \
                                    ((time.time() - modify_timer) >= glob.MODIFY_LIMIT_ORDER_TIMEOUT)) or (use_market_price):
                                        
                                        # Update order type to MKT order
                                        active_orders['OrderType'][order_idx] = "MKT"
                                        order['OrderType'] = "MKT"


                                    # Modify the paper order with a new price
                                    is_modified = self._wb.modify_order(order=active_orders['FullOrder'][order_idx], 
                                                                        price=new_price, action=active_orders['Action'][order_idx], 
                                                                        orderType=active_orders['OrderType'][order_idx],
                                                                        enforce='DAY', 
                                                                        quant=active_orders['Quantity'][order_idx])

                                    # If modified order successfully processed
                                    if is_modified:
                                        logging.info(f"[{self._bot_name}] Successfully modified {active_orders['Action'][order_idx]} order #{order['OrderID']} for {active_orders['Ticker'][order_idx]}!")

                                    # Else modified order not processed
                                    else:
                                        logging.error(f"[{self._bot_name}] Unable to modify {active_orders['Action'][order_idx]} order #{order['OrderID']} for {active_orders['Ticker'][order_idx]}!")

                                        # Decrement the number of modify attempts remaining
                                        failed_modify_attempts -= 1

                                        # If maximum attempts have been reached
                                        if failed_modify_attempts == 0:

                                            # Cancel order
                                            is_cancelled = self.cancel_order(order_id=order["OrderID"], 
                                                                            order_type=active_orders['OrderType'][order_idx])

                            # Else if order not in active paper orders table
                            elif (not found) or (order['OrderID'] not in active_orders['OrderID']):

                                # Order has been filled or cancelled
                                order['Filled'] = True


                        # If paper order has not been cancelled and network connection established and market open
                        if (not is_cancelled) and (self._network_connected) and (glob.MARKET_OPEN.is_set()):

                            logging.info(f"[{self._bot_name}] {order['Action']} order #{order['OrderID']} for {order['Ticker']} has been filled!")

                        # If market closed
                        if dt.datetime.now().time() >= glob.MARKET_CLOSE_TIME:

                            # Cancel order
                            is_cancelled = self.cancel_order(order_id=order['OrderID'], 
                                                            order_type=order['OrderType'])

                        # Mark working order queue task as complete
                        glob.WORKING_ORDERS_QUEUE.task_done()

                # *** Connection Error ***
                except requests.exceptions.ConnectionError as e:
                    # Verify internet connection
                    self._network_connected = misc.is_network_connected()

                    # If no internet connection established
                    if not self._network_connected:
                        
                        # Wait for connection to re-establish
                        self._network_connected = misc.wait_for_network_connection()

                    # Else internet connection established
                    else:
                        logging.warning(f"[{self._bot_name}] Internet connection established!. . . CONNECTION ERROR: {e}")

                # *** Unknown Error ***
                except Exception:
                    logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

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

        logging.info(f"[{self._bot_name}] Successfully exited thread: {self._manage_paper_orders_thread.getName()}")

        return



    '''
    =========================================================================
    * manage_stop_loss()                                                    *
    =========================================================================
    * This function will manage active buy/sell orders to ensure that they  *
    * get filled.                                                           *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def manage_stop_loss(self):
        try:
            # If paper trading
            if self._paper_trading:
                self.load_stop_loss_tracker()

            # Loop while market open and network connection is established
            while (glob.MARKET_OPEN.is_set()) and (self._network_connected):
                try:
                    active_trades = self.get_active_trades()        # Get active trades (paper/live trading)

                    # If not paper trading
                    if not self._paper_trading:
                        active_orders = self.get_active_orders()    # Get active orders (live trading only)

                    # Iterate through all active trades
                    for trade in active_trades:

                        # If paper trading AND trade not in stop loss tracker list
                        if (self._paper_trading) and (trade['Ticker'] not in self._stop_loss_tracker.keys()):
                            # Place trade in stop loss tracker list
                            self._stop_loss_tracker[trade['Ticker']] = {
                                "StopLossPrice"     : round((trade['Price'] - (trade['Price'] * self._default_SL)), 2),     # Set stop loss price
                                "StopLossPercent"   : -self._default_SL                                                     # Set stop loss percent
                            }

                        # Else if live trading
                        elif not self._paper_trading:
                            # Find the index of the stop loss order associated with the active trade
                            filt_order  = filter(lambda order: order.get("Ticker") == trade["Ticker"] and order.get("Pointer") == trade["Pointer"], active_orders)
                            order_match = next(filt_order, None)

                            # If stop loss order for active trade not found (stop loss hit)
                            if not order_match:

                                if self._debug:
                                    logging.info(f"++ [{self._bot_name}] (DEBUG) ACTIVE ORDERS: {active_orders}")

                                # If active trade in stop loss tracker
                                if trade['Ticker'] in self._stop_loss_tracker.keys():

                                    # Remove trade from stop loss tracker
                                    logging.info(f"++ [{self._bot_name}] Removing trade [{trade['Ticker']} | {trade['StrikePrice']} | {trade['Direction']} | {trade['ExpDate']}] from stop loss tracker list!")
                                    del self._stop_loss_tracker[trade['Ticker']]

                                    if self._debug:
                                        logging.info(f"++ [{self._bot_name}] (DEBUG) STOP LOSS TRACKER LIST: {self._stop_loss_tracker}")

                                continue    # Return to beginning of active trades for-loop

                            # If active trade not in stop loss tracker list AND stop order associated with active trade found
                            if (trade['Ticker'] not in self._stop_loss_tracker.keys()) and (order_match):
                                # Place trade in stop loss tracker list
                                self._stop_loss_tracker[trade['Ticker']] = {
                                    "StopLossPrice": round(order_match['StopLoss'], 2),     # Set stop loss price
                                    "StopLossPercent": -self._default_SL,                   # Set stop loss percent
                                    "Modified": False                                       # Set modified status flag
                                }

                                # If stop loss price not provided
                                if order_match['StopLoss'] <= 0.0:
                                    # Update stop loss price to default price
                                    self._stop_loss_tracker[trade['Ticker']]["StopLossPrice"] = round((trade['Price'] - (trade['Price'] * self._default_SL)), 2)

                        # If paper trading
                        if self._paper_trading:

                            # If last price is less than or equal to stop loss price (stop loss hit)
                            if trade['LastPrice'] <= self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']:
                                logging.info(f"++ [{self._bot_name}] Stopped out of trade !!! ==> [{trade['Ticker']}]")

                                # If negative shares owned (shorting stock - equivalent to PUT direction)
                                if trade['Quantity'] < 0:

                                    # Place a paper buy order at MKT (ALL OUT)
                                    self.place_paper_order(action="BUY",
                                                        ticker=trade['Ticker'], 
                                                        percent=1.0, 
                                                        short=True, 
                                                        order_type="MKT")

                                # Else positive shares owned (not shorting stock - equivalent to CALL direction)
                                else:

                                    # Place a paper sell order at MKT (ALL OUT)
                                    self.place_paper_order(action="SELL", 
                                                        ticker=trade['Ticker'], 
                                                        percent=1.0, 
                                                        short=False, 
                                                        order_type="MKT")

                                # Remove paper trade from stop loss tracker
                                del self._stop_loss_tracker[trade['Ticker']]

                            # Else last price is greater than stop loss price (stop loss not hit)
                            else:

                                # Get the open P/L percent for the active paper trade
                                open_PL_percent = trade['ProfitLossPercent']

                                # If open P/L percent is greater than 10% AND less than 20% AND initial stop loss percent for ticker has not been updated
                                if ((open_PL_percent >= 0.1) and (open_PL_percent < 0.2)) and \
                                    (self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'] == -self._default_SL):

                                    # Set stop loss price at break even and update stop loss percent
                                    self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']   = trade['Price']
                                    self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'] = glob.STOP_LOSS_ADJUSTMENT_PERCENT

                                # Else if open P/L percent is greater than 20% AND difference between P/L percent and 'StopLossPercent' is greater than equal to 10%
                                elif (open_PL_percent >= 0.2) and \
                                    ((open_PL_percent - self._stop_loss_tracker[trade['Ticker']]['StopLossPercent']) >= glob.STOP_LOSS_ADJUSTMENT_PERCENT):

                                    # Update stop loss price and stop loss percent
                                    self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']   = round((trade['Price'] + (trade['Price'] * self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'])), 2)
                                    self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'] += glob.STOP_LOSS_ADJUSTMENT_PERCENT

                        # Else live trading
                        else:
                            # Get the open P/L percent for the active trade
                            open_PL_percent = trade['ProfitLossPercent']

                            # If open P/L percent is greater than 10% AND less than 20% AND initial stop loss percent for ticker has not been updated
                            if ((open_PL_percent >= 0.1) and (open_PL_percent < 0.2)) and (trade['Ticker'] in self._stop_loss_tracker.keys()) and \
                                (self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'] == -self._default_SL):

                                # Set stop loss price at break even and update stop loss percent
                                self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']   = trade['Price']
                                self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'] = glob.STOP_LOSS_ADJUSTMENT_PERCENT
                                self._stop_loss_tracker[trade['Ticker']]['Modified']        = True

                                if self._debug:
                                    logging.info(f"++ [{self._bot_name}] (DEBUG) BREAK EVEN STOP LOSS CONDITION\n" +
                                                                        f"==> STOP LOSS PRICE: {self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']}\n" +
                                                                        f"==> STOP LOSS PERCENT: {self._stop_loss_tracker[trade['Ticker']]['StopLossPercent']}")

                            # Else if open P/L percent is greater than 20% AND difference between P/L percent and 'StopLossPercent' is greater than equal to 10%
                            elif (open_PL_percent >= 0.2) and (trade['Ticker'] in self._stop_loss_tracker.keys()) and \
                                ((open_PL_percent - self._stop_loss_tracker[trade['Ticker']]['StopLossPercent']) >= glob.STOP_LOSS_ADJUSTMENT_PERCENT):

                                # Update stop loss price and stop loss percent
                                self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']   = round((trade['Price'] + (trade['Price'] * self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'])), 2)
                                self._stop_loss_tracker[trade['Ticker']]['StopLossPercent'] += glob.STOP_LOSS_ADJUSTMENT_PERCENT
                                self._stop_loss_tracker[trade['Ticker']]['Modified']        = True

                                if self._debug:
                                    logging.info(f"++ [{self._bot_name}] (DEBUG) STOP LOSS ADJUST CONDITION\n" +
                                                                        f"==> STOP LOSS PRICE: {self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']}\n" +
                                                                        f"==> STOP LOSS PERCENT: {self._stop_loss_tracker[trade['Ticker']]['StopLossPercent']}")

                            # If stop loss modified AND active stop order associated with active trade found
                            if (trade['Ticker'] in self._stop_loss_tracker.keys()) and (self._stop_loss_tracker[trade['Ticker']]['Modified']):

                                # Modify stop loss order to new stop loss price
                                is_modified = self._wb.modify_order(order_id=order_match['OrderID'], 
                                                                    stock=order_match['Ticker'], 
                                                                    price=self._stop_loss_tracker[trade['Ticker']]['StopLossPrice'],
                                                                    action=order_match['Action'], 
                                                                    orderType=order_match['OrderType'], 
                                                                    enforce="GTC", 
                                                                    quant=order_match['Quantity'])

                                # If stop loss order modified
                                if is_modified:
                                    logging.info(f"++ [{self._bot_name}] Stop loss order modified for [{trade['Ticker']} | {trade['StrikePrice']} | {trade['Direction']} | {trade['ExpDate']}] @{self._stop_loss_tracker[trade['Ticker']]['StopLossPrice']}")
                                    
                                    # Reset stop loss modified status
                                    self._stop_loss_tracker[trade['Ticker']]['Modified'] = False


                # *** Connection Error ***
                except requests.exceptions.ConnectionError as e:
                    # Verify internet connection
                    self._network_connected = misc.is_network_connected()

                    # If no internet connection established
                    if not self._network_connected:
                        
                        # Wait for connection to re-establish
                        self._network_connected = misc.wait_for_network_connection()

                    # Else internet connection established
                    else:
                        logging.warning(f"[{self._bot_name}] Internet connection established!. . . CONNECTION ERROR: {e}")

                # *** Unknown Error ***
                except Exception:
                    logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

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

        logging.info(f"[{self._bot_name}] Successfully exited thread: {self._manage_stop_loss_thread.getName()}")

        return



    # '''
    # =========================================================================
    # * manage_paper_stop_loss()                                              *
    # =========================================================================
    # * This function will manage stop losses for active paper orders.        *
    # *                                                                       *
    # *   INPUT:                                                              *
    # *         None                                                          *
    # *                                                                       *
    # *   OUPUT:                                                              *
    # *         None                                                          *
    # =========================================================================
    # '''
    # def manage_paper_stop_loss(self):

    #     try:
    #         # Load stop loss tracker
    #         self.load_stop_loss_tracker()

    #         # Loop while market open and network connection is established
    #         while (glob.MARKET_OPEN.is_set()) and (self._network_connected):

    #             try:
    #                 # Get active paper trades
    #                 active_paper_trades = self.get_active_trades()

    #                 # Iterate through all paper trades
    #                 for paper_trade in active_paper_trades:

    #                     # If trade not in stop loss tracker list
    #                     if active_paper_trades['Ticker'][i] not in self._stop_loss_tracker.keys():

    #                         # Place trade in stop loss tracker list
    #                         self._stop_loss_tracker[active_paper_trades['Ticker'][i]] = {

    #                             # Initialize with a -20% stop loss price and percent
    #                             "StopLossPrice": round((active_paper_trades['Price'][i] - (active_paper_trades['Price'][i] * self._default_SL)), 2),
    #                             "StopLossPercent": -self._default_SL
    #                         }

    #                     # If last price is less than or equal to stop loss price (stop loss hit)
    #                     if active_paper_trades['LastPrice'][i] <= self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPrice']:

    #                         logging.info(f"[{self._bot_name}] Stopped out of trade !!! ==> [{active_paper_trades['Ticker'][i]}]")

    #                         # If negative shares owned (shorting stock - equivalent to PUT direction)
    #                         if active_paper_trades['Quantity'][i] < 0:

    #                             # Place a paper buy order at MKT (ALL OUT)
    #                             self.place_paper_order(action="BUY",
    #                                                    ticker=active_paper_trades['Ticker'][i], 
    #                                                    percent=1.0, 
    #                                                    short=True, 
    #                                                    order_type="MKT")

    #                         # Else positive shares owned (not shorting stock - equivalent to CALL direction)
    #                         else:

    #                             # Place a paper sell order at MKT (ALL OUT)
    #                             self.place_paper_order(action="SELL", 
    #                                                    ticker=active_paper_trades['Ticker'][i], 
    #                                                    percent=1.0, 
    #                                                    short=False, 
    #                                                    order_type="MKT")

    #                         # Remove paper trade from stop loss tracker
    #                         del self._stop_loss_tracker[active_paper_trades['Ticker'][i]]

    #                     # Else last price is greater than stop loss price (stop loss not hit)
    #                     else:

    #                         # Get the open P/L percent for the active paper trade
    #                         open_PL_percent = active_paper_trades['ProfitLossPercent'][i]

    #                         # If open P/L percent is greater than 10% and less than 20% and initial stop loss percent for ticker has not been updated
    #                         if ((open_PL_percent >= 0.1) and (open_PL_percent < 0.2)) and \
    #                             (self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPercent'] == -self._default_SL):

    #                             # Set stop loss price at break even and update stop loss percent
    #                             self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPrice'] = active_paper_trades['Price'][i]
    #                             self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPercent'] = glob.STOP_LOSS_ADJUSTMENT_PERCENT

    #                         # Else if open P/L percent is greater than 20% and difference between P/L percent and 'StopLossPercent' is greater than equal to 10%
    #                         elif (open_PL_percent >= 0.2) and \
    #                              ((open_PL_percent - self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPercent']) >= glob.STOP_LOSS_ADJUSTMENT_PERCENT):

    #                             # Update stop loss price and stop loss percent
    #                             self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPrice'] = round((active_paper_trades['Price'][i] + (active_paper_trades['Price'][i] * \
    #                                                                                                                 self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPercent'])), 2)
    #                             self._stop_loss_tracker[active_paper_trades['Ticker'][i]]['StopLossPercent'] += glob.STOP_LOSS_ADJUSTMENT_PERCENT

    #             # *** Connection Error ***
    #             except requests.exceptions.ConnectionError as e:
    #                 # Verify internet connection
    #                 self._network_connected = misc.is_network_connected()

    #                 # If no internet connection established
    #                 if not self._network_connected:
                        
    #                     # Wait for connection to re-establish
    #                     self._network_connected = misc.wait_for_network_connection()

    #                 # Else internet connection established
    #                 else:
    #                     logging.warning(f"[{self._bot_name}] Internet connection established!. . . CONNECTION ERROR: {e}")

    #             # *** Unknown Error ***
    #             except Exception:
    #                 logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

    #     # *** Keyboard Exit ***
    #     except KeyboardInterrupt:
    #         # Set program shutdown event
    #         if not glob.PROGRAM_SHUTDOWN.is_set():
    #             glob.PROGRAM_SHUTDOWN.set()

    #     # Save stop loss tracker
    #     self.save_stop_loss_tracker()

    #     # If thread stopped due to program shutdown
    #     if glob.PROGRAM_SHUTDOWN.is_set():
    #         logging.info(f"[{self._bot_name}] Exiting due to program shutdown!")

    #     # If thread stopped due to network connection
    #     if not self._network_connected:
    #         logging.info(f"[{self._bot_name}] Exiting due to network connection!")

    #     logging.info(f"[{self._bot_name}] Successfully exited thread: {self._manage_paper_stop_loss_thread.getName()}")

    #     return



    #########################################################################
    #                 G E N E R A L   F U N C T I O N S                     #
    #########################################################################
    '''
    =========================================================================
    * get_option_trade_id()                                                 *
    =========================================================================
    * This function will get and return the id associated with an option    *
    * contract.                                                             *
    *                                                                       *
    *   INPUT:                                                              *
    *                     ticker (str) - Stock symbol.                      *
    *               strike_price (str) - Expected price the stock will      *
    *                                    reach.                             *
    *                  direction (str) - Call (Bullish) or Put (Bearish).   *
    *         exp_date (datetime.date) - Expiration date of the option      *
    *                                    contract.                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         This function will return a tuple that contains:              *
    *           +              id_found (bool) - Option ID found.           *
    *           +              option_id (str) - ID associated with the     *
    *                                            option contract.           *
    *           + new_exp_date (datetime.date) - Updated option expiration  *
    *                                            date if input expiration   *
    *                                            date is invalid.           *
    =========================================================================
    '''
    def get_option_trade_id(self, ticker="", strike_price="", direction="", exp_date=None):
        try:
            # Get option contract details for ticker that match strike price, direction, and expiration date
            options_list = self._wb.get_options_by_strike_and_expire_date(stock=ticker, 
                                                                          expireDate=exp_date.strftime(glob.DATE_FORMAT_YYYY_MM_DD), 
                                                                          strike=strike_price, 
                                                                          direction=direction)

            # If option contract details are available
            if options_list:

                # Set ID found status, option contract ID, and new expiration date (Valid data)
                id_found = True
                option_id = options_list[0][direction]['tickerId']
                new_exp_date = exp_date

            # Else option contract details are not available
            else:

                # Set ID found status, option contract ID, and new expiration date (Invalid data)
                id_found = False
                option_id = ""
                new_exp_date = exp_date

                # Initialize expiration date match and previous difference in days
                exp_date_match = None
                prev_diff_days = 999

                # Get option expiration dates for ticker
                option_exp_dates = self._wb.get_options_expiration_dates(stock=ticker)

                # Iterate through all option expiration dates
                for opt_exp_date in option_exp_dates:

                    # Determine the difference in days between option expiration date and expiration date from alert
                    opt_date = parse(opt_exp_date['date']).date()
                    delta = abs(opt_date - exp_date)

                    # If difference in days is less than previous difference in days
                    if delta.days < prev_diff_days:
                        prev_diff_days = delta.days
                        exp_date_match = opt_date

                # Retry search for option ID using new expiration date match
                options_list = self._wb.get_options_by_strike_and_expire_date(stock=ticker, 
                                                                              expireDate=exp_date_match.strftime(glob.DATE_FORMAT_YYYY_MM_DD), 
                                                                              strike=strike_price, 
                                                                              direction=direction)

                # If option contract details are available
                if options_list:

                    # Set ID found status, option contract ID, and new expiration date (Valid data)
                    id_found = True
                    option_id = options_list[0][direction]['tickerId']
                    new_exp_date = exp_date_match

        # *** Invalid Ticker ***
        except ValueError:
            logging.error(f"[{self._bot_name}] TickerId could not be found for stock {ticker}!")

            # Set ID found status, option contract ID, and new expiration date (Invalid data)
            id_found = False
            option_id = ""
            new_exp_date = exp_date

        # *** Unknown Error ***
        except Exception:
            logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

            # Set ID found status, option contract ID, and new expiration date (Invalid data)
            id_found = False
            option_id = ""
            new_exp_date = exp_date

        return (id_found, option_id, new_exp_date)



    '''
    =========================================================================
    * get_quantity_buy()                                                    *
    =========================================================================
    * This function will determine the number of option contracts or shares *
    * to purchase.                                                          *
    *                                                                       *
    *   INPUT:                                                              *
    *              price (float) - The price to pay per option contract or  *
    *                              share.                                   *
    *         percentage (float) - The percentage of cash to invest.        *
    *                                                                       *
    *   OUPUT:                                                              *
    *         quant (int) - The number of contracts or shares to purchase.  *
    =========================================================================
    '''
    def get_quantity_buy(self, price=0.0, percentage=0.0):
        try:

            # Get recent account information
            account_info = self.get_account_info()

            # If paper trading
            if self._paper_trading:

                # Calculate the quantity of stock shares to purchase
                quant = int((account_info["Cash Balance"] * percentage) / price)

            # Else live trading
            else:

                # Calculate the quantity of option contracts to purchase
                quant = int((account_info["Option BP"] * percentage) / (price * 100))

        # *** Zero Price ***
        except ZeroDivisionError:
            logging.error(f"[{self._bot_name}] Price needs to be greater than zero!")
            quant = 0

        # *** Unknown Error ***
        except Exception:
            logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

        # If debugging enabled
        if self._debug:
            logging.info(f"[{self._bot_name}] (DEBUG) [Price: {price} | Percent: {percentage}] ==> Quantity: {quant}")

        return quant



    '''
    =========================================================================
    * get_quantity_sell()                                                   *
    =========================================================================
    * This function will determine the number of option contracts or shares *
    * to sell.                                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *               ticker (str) - The stock symbol of the trade.           *
    *            option_id (str) - The contract ID of the stock option.     *
    *         percentage (float) - Percentage of option contracts or shares *
    *                              to sell.                                 *
    *                                                                       *
    *   OUPUT:                                                              *
    *         quant (int) - The number of contracts or shares to sell.      *
    =========================================================================
    '''

    def get_quantity_sell(self, ticker="", option_id="", percentage=0.0):
        try:

            # Wait until trade table has been updated with the filled order
            found, active_trades = self.wait_for_trade_in_table(id=option_id)

            # # Get current active trades
            # active_trades = self.get_active_trades()

            # If paper trading
            if self._paper_trading:

                # Get the number of shares held that correspond to the ticker
                if (found) and (ticker in active_trades['Ticker']):
                    id_idx = active_trades['Ticker'].index(ticker)
                    quant_held = abs(active_trades['Quantity'][id_idx])
                else:
                    quant_held = 0

            # Else live trading
            else:

                # Get the number of contracts held that correspond to the option ID
                if (found) and (option_id in active_trades['OptionID']):
                    id_idx = active_trades['OptionID'].index(option_id)
                    quant_held = active_trades['Quantity'][id_idx]
                else:
                    quant_held = 0


            # If selling a certain number of contracts/shares (i.e. 1-9 contracts/shares)
            if (percentage >= 0.01) and (percentage <= 0.09):

                quant = int(percentage * 100)

            # Else sell percentage of contracts/shares held
            else:
                quant = quant_held * percentage

                # If quantity to sell is between zero (0) and one (1)
                if (quant > 0) and (quant < 1):

                    # Adjust quantity to sell to one (1)
                    quant = 1

                # Else quantity to sell is zero (0) or greater than equal to one (1)s
                else:
                    quant = int(quant)


            # If quantity to sell is more than quantity held
            if quant > quant_held:
                quant = quant_held

            # If debugging enabled
            if self._debug:
                logging.info(f"[{self._bot_name}] (DEBUG) [Quantity Held: {quant_held} | Percent: {percentage}] ==> Quantity Sell: {quant}")

        # *** Trade ID or Option ID Not Found ***
        except (IndexError, KeyError):
            logging.error(f"[{self._bot_name}] Trade ID or Option ID not found!")
            quant = 0

        # *** Unknown Error ***
        except Exception:
            logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)
            quant = 0

        return quant



    '''
    =========================================================================
    * get_stock_quote()                                                     *
    =========================================================================
    * This function will get the current price of a stock or options        *
    * contract.                                                             *
    *                                                                       *
    *   INPUT:                                                              *
    *            ticker (str) - The stock symbol.                           *
    *         option_id (str) - The id associated with an option trade.     *
    *                                                                       *
    *   OUPUT:                                                              *
    *             quote (float) - The current price of a stock or options   *
    *                             contract.                                 *
    *   use_market_price (bool) - Update order type to 'MKT' order.         *
    =========================================================================
    '''
    def get_stock_quote(self, ticker="", option_id=""):
        try:
            # If ticker or option id not provided
            if (not ticker) or (not option_id):
                raise ValueError

            # Initialize market price order status
            use_market_price = False

            # If live trading
            if not self._paper_trading:

                # Get the price of the option contract for the ticker
                quote = self._wb.get_option_quote(stock=ticker, 
                                                  optionId=option_id)

                # If quote data available and 'Ask' and 'Bid' lists available
                if (quote['data']) and (quote['data'][0]['askList']) and (quote['data'][0]['bidList']):

                    # Get the 'Bid' and 'Ask' price
                    ask_price = float(quote['data'][0]['askList'][0]['price'])
                    bid_price = float(quote['data'][0]['bidList'][0]['price'])

                # Else quote data not available or 'Ask' and 'Bid' lists not available
                else:
                    ask_price = 0.0
                    bid_price = 0.0

            # Else paper trading
            else:

                # Get the price of the stock share for the ticker
                quote = self._wb.get_quote(stock=ticker)

                # If 'Ask' and 'Bid' lists available
                if (quote['askList']) and (quote['bidList']):

                    # Get the 'Bid' and 'Ask' price
                    ask_price = float(quote['askList'][0]['price'])
                    bid_price = float(quote['bidList'][0]['price'])

                # Else 'Ask' and 'Bid' lists not available
                else:
                    ask_price = 0.0
                    bid_price = 0.0

            # Calculate the average of the 'Bid' and 'Ask' price
            price = round(((ask_price + bid_price) / 2), 2)

            # If the difference between the 'Ask' and 'Bid' price is less than the max spread difference
            if ((ask_price - bid_price) * 100) < glob.MAX_SPREAD_DIFF:
                use_market_price = True     # Change order type to market order

        # *** Keywords 'data' or 'askList' or 'bidList' Not Found ***
        except KeyError:
            logging.error(f"[{self._bot_name}] Could not find 'data', 'askList', or 'bidList'!")
            price = 0.0
            use_market_price = False

        # *** Invalid Ticker Provided ***
        except ValueError:
            # If ticker not provided
            if not ticker:
                logging.error(f"[{self._bot_name}] Missing ticker!. . . Cound not get stock quote!")
                
            # Else ticker provided but not found
            else:
                logging.error(f"[{self._bot_name}] Cound not find stock quote for {ticker}!")

            # If option id not provided
            if not option_id:
                logging.error(f"[{self._bot_name}] Missing option id!. . . Cound not get stock quote!")

            price = 0.0
            use_market_price = False

        # *** Internet Connection Down ***
        except requests.exceptions.ConnectionError as e:
            logging.error(f"[{self._bot_name}] No internet connection established!. . . Could not get stock quote for {ticker}!")
            logging.error(f"[{self._bot_name}] CONNECTION ERROR: {e}")
            price = 0.0
            use_market_price = False

        # *** Unknown Error ***
        except Exception:
            logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)
            price = 0.0
            use_market_price = False

        # If debugging enabled
        if self._debug:

            # If not paper trading
            if not self._paper_trading:
                logging.info(f"[{self._bot_name}] (DEBUG) [Ticker: {ticker} | OptionID: {option_id}] ==> Price: {price}")

            # Else paper trading
            else:
                logging.info(f"[{self._bot_name}] (DEBUG) [Ticker: {ticker} | OptionID: N/A] ==> Price: {price}")

        return price, use_market_price



    '''
    =========================================================================
    * cancel_order()                                                        *
    =========================================================================
    * This function will cancel a single options or paper trade order.      *
    *                                                                       *
    *   INPUT:                                                              *
    *           order_id (str) - The id of order being canceled.            *
    *         order_type (str) - The type of order being canceled           *
    *                            (BUY/SELL/STOP).                           *
    *                                                                       *
    *   OUPUT:                                                              *
    *         order_cancelled (bool) - Cancelled order status.              *
    =========================================================================
    '''
    def cancel_order(self, order_id="", order_type=""):

        # Cancel an open order using the order ID
        status = self._wb.cancel_order(order_id=order_id)

        # If successfully cancelled order
        if status:
            logging.info(f"[{self._bot_name}] Successfully canceled {order_type} order #{order_id}!")
            order_cancelled = True

        # Else unsuccessful cancellation
        else:
            logging.error(f"[{self._bot_name}] Unable to cancel {order_type} order #{order_id}!")
            order_cancelled = False

        return order_cancelled



    '''
    =========================================================================
    * cancel_stop_loss_order()                                              *
    =========================================================================
    * This function will cancel an existing stop loss order for an option   *
    * contract in order to place a sell order on that same option contract. *
    *                                                                       *
    *   INPUT:                                                              *
    *                ticker (str) - The stock symbol of the trade.          *
    *                strike (str) - The strike price of the option          *
    *                               contract.                               *
    *             direction (str) - Call/Put direction of the option        *
    *                               contract.                               *
    *         exp_date (datetime) - The expiration date of the option       *
    *                               contract.                               *
    *                                                                       *
    *   OUPUT:                                                              *
    *         order_cancelled (bool) - Cancelled stop loss order.           *
    =========================================================================
    '''

    def cancel_stop_loss_order(self, ticker="", strike="", direction="", exp_date=None):
        # Initialize order cancelled status
        order_cancelled = False

        # If ticker, strike price, direction, and expiration date not provided
        if (not ticker) and (not strike) and (not direction) and (not exp_date):
            logging.warning(f"[{self._bot_name}] Need a ticker symbol, strike price, direction, and expiration date in order to cancel a stop loss order!")

        # Else ticker, strike price, direction, and expiration date provided
        else:

            # Get current active trades and orders
            active_trades = self.get_active_trades()
            active_orders = self.get_active_orders()

            # Find the index of the pointer to the active orders table
            pointer_idx = -1
            for i in range(len(active_trades['OptionID'])):
                if active_trades['Ticker'][i] == ticker and \
                   active_trades['StrikePrice'][i] == strike and \
                   active_trades['Direction'][i] == direction and \
                   active_trades['ExpDate'][i] == exp_date:
                   pointer_idx = i
                   break

            # If pointer index not found
            if pointer_idx < 0:
                logging.warning(f"[{self._bot_name}] Could not find pointer to active orders table for [{ticker} | {strike} | {direction} | {exp_date}]!")
                return order_cancelled
                
            # Find the index of the active order
            order_idx = -1
            for i in range(len(active_orders['OrderID'])):
                if active_orders['Ticker'][i] == ticker and \
                   active_orders['OrderType'][i] == "STP" and \
                   active_orders['Pointer'][i] == active_trades['Pointer'][pointer_idx]:
                   order_idx = i
                   break

            # If active order index not found
            if order_idx < 0:
                logging.warning(f"[{self._bot_name}] Could not find active stop order for [{ticker} | {strike} | {direction} | {exp_date}]!")
                return order_cancelled

            # If market open and developer mode not enabled
            if (glob.MARKET_OPEN.is_set()) and (not glob.DEVELOPER_MODE.is_set()):

                # Use active order ID to cancel the stop order
                order_id = active_orders['OrderID'][order_idx]

                logging.info(f"[{self._bot_name}] Canceling STP order #{order_id} for {ticker}!")

                order_cancelled = self.cancel_order(order_id=order_id, 
                                                    order_type=active_orders['OrderType'][order_idx])

                # If stop order cancelled
                if order_cancelled:
                    logging.info(f"[{self._bot_name}] STP order #{order_id} for {ticker} has been successfully cancelled!")

                # Else stop order not cancelled
                else:
                    logging.error(f"[{self._bot_name}] Unable to cancel STP order #{order_id} for {ticker}!")

        return order_cancelled



    '''
    =========================================================================
    * wait_for_trade_in_table()                                             *
    =========================================================================
    * This function will check and wait for a specific trade to appear in   *
    * the active trades table.                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *              id (str) - The ID of the active trade to search for.     *
    *         timeout (int) - The max time to wait for an option trade.     *
    *                                                                       *
    *   OUPUT:                                                              *
    *        success (bool) - Trade found status.                           *
    *  active_trades (dict) - Dictionary of all active trades.              *
    =========================================================================
    '''
    def wait_for_trade_in_table(self, id="", timeout=glob.MAX_WAIT_TIMEOUT):
        # Initialize success status
        success = False
        
        # If ID not provided
        if not id:
            logging.error(f"[{self._bot_name}] No trade/option ID provided to wait for!")
            return success, None

        # Initialize start time and active trades
        elapsed_time = time.time()
        active_trades = None

        # If paper trading
        if self._paper_trading:

            # Wait until trade table has been updated with the trade ID
            active_trades = self.get_active_trades()
            while(id not in active_trades['TradeID']) and \
                (time.time()-elapsed_time < timeout):
                active_trades = self.get_active_trades()

        # Else live trading
        else:

            # Wait until trade table has been updated with the option ID
            active_trades = self.get_active_trades()
            while(id not in active_trades['OptionID']) and \
                (time.time()-elapsed_time < timeout):
                active_trades = self.get_active_trades()

        # If timeout not reached
        if time.time()-elapsed_time < timeout:
            success = True      # Trade found
        
        return success, active_trades



    '''
    =========================================================================
    * wait_for_order_in_table()                                             *
    =========================================================================
    * This function will check and wait for a specific order to appear in   *
    * the active orders table.                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *         orderId (str) - The ID of the option order to search for.     *
    *         timeout (int) - The max time to wait for an option order.     *
    *                                                                       *
    *   OUPUT:                                                              *
    *        success (bool) - Order found status.                           *
    =========================================================================
    '''
    def wait_for_order_in_table(self, orderId="", timeout=glob.MAX_WAIT_TIMEOUT):
        # Initialize success status
        success = False
        
        # If order ID not provided
        if not orderId:
            logging.error(f"[{self._bot_name}] No order ID provided to wait for!")
            return (success, None)

        # Initialize start time and active orders
        elapsed_time = time.time()
        active_orders = None

        # If paper trading
        if self._paper_trading:

            # Wait until order table has been updated with the order ID
            active_orders = self.get_active_orders()
            while(orderId not in active_orders['OrderID']) and \
                (time.time()-elapsed_time < timeout):
                active_orders = self.get_active_orders()

        # Else live trading
        else:

            # Wait until order table has been updated with the order ID
            active_orders = self.get_active_orders()[1]
            while(orderId not in active_orders['OrderID']) and \
                (time.time()-elapsed_time < timeout):
                active_orders = self.get_active_orders()[1]

        # If timeout not reached
        if time.time()-elapsed_time < timeout:
            success = True      # Order found
        
        return success, active_orders



    '''
    =========================================================================
    * get_mfa_pin_from_email()                                              *
    =========================================================================
    * This function will extract the Webull verification pin from a user's  *
    * email address when using a Multi-Factor Authentication (MFA) login.   *
    *                                                                       *
    *   INPUT:                                                              *
    *         sms_user (str) - Email address.                               *
    *         sms_pass (str) - Email password.                              *
    *                                                                       *
    *   OUPUT:                                                              *
    *         mfa_pin (str) - The MFA verification pin.                     *
    =========================================================================
    '''
    async def get_mfa_pin_from_email(self, sms_user="", sms_pass=""):
        # Initialize MFA pin
        mfa_pin = ""

        # Setup and log into IMAP server
        imap_client = imap.IMAP4_SSL(host=glob.SMS_IMAP_HOST, port=glob.SMS_IMAP_PORT, ssl_context=glob.SMS_SSL)
        await imap_client.wait_hello_from_server()
        response = await imap_client.login(user=sms_user, password=sms_pass)

        # If successful login
        if response.result == 'OK':

            # Access inbox
            await imap_client.select(mailbox="INBOX")

            logging.info(f"[{self._bot_name}] Searching for MFA verification pin. . .")

            # Wait till verification email has been found
            while True:

                # Search for emails from Webull support and contain keyword "verify" in subject header
                response = await imap_client.uid_search(f'FROM "Webull" SUBJECT "Verify" SINCE "{dt.date.today().strftime(glob.DATE_FORMAT_DD_MONTH_YYYY)}"')

                # If results found during search
                if response.result == "OK":
                    break

                # Else wait ten (10) seconds and search again
                else:
                    time.sleep(10)

            # Get message uids
            uids = response.lines[0].split()

            # Get the first MFA verification pin that has not expired (pins expire after 30 minutes)
            for uid in uids:

                # If uid is not empty
                if uid:

                    # Fetch uid data
                    response = await imap_client.uid('FETCH', uid.decode('utf-8'), "(RFC822)")

                    # If successfully fetched message contents
                    if response.result == "OK":

                        # Decode message and get timestamp date and time
                        message = email.message_from_bytes(response.lines[1])
                        timestamp = email.utils.parsedate_to_datetime(message.get('Date')).astimezone(tz.tzlocal())
                        message_date = timestamp.date()
                        message_time = timestamp.time()

                        # If MFA verification email is same day and no more than 30 minutes has passed since message received
                        if (not mfa_pin) and (abs((dt.date.today() - message_date).days) < 1) and \
                           (abs((dt.datetime.combine(dt.date.today(), message_time) - dt.datetime.now()).total_seconds()) < glob.MFA_PIN_TIMEOUT):

                            # Search HTML body for text that contains MFA access code/pin
                            html_tree = etree.HTML(message.get_payload())
                            pin_found = html_tree.xpath("//text()[number(.) = .]")[0]

                            # If no mfa pin set
                            if not mfa_pin:
                                logging.info(f"[{self._bot_name}] MFA verification pin found!")
                                mfa_pin = pin_found

                    # Mark email for deletion
                    response = await imap_client.uid('STORE', uid.decode('utf-8'), '+FLAGS', '\\Deleted')

            # Delete marked emails, close out of inbox, and logout of IMAP client
            response = await imap_client.expunge()
            response = await imap_client.close()
            response = await imap_client.logout()

        # Else unsuccessful login
        else:
            logging.warning(f"[{self._bot_name}] Invalid SMS login credentials!")

        return mfa_pin



    '''
    =========================================================================
    * show_account_info()                                                   *
    =========================================================================
    * This function will show webull trading account information.           *
    *                                                                       *
    *   INPUT:                                                              *
    *         account (dict) - Trading account information.                 *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def show_account_info(self, account={}):

        # If no account data provided
        if not account:
            logging.warning(f"[{self._bot_name}] No account information to display!")
            return

        # Create trading account information table
        account_df = pd.DataFrame.from_dict(account, orient='index')
        account_df.index.name = "WEBULL ACCOUNT INFO"
        account_df.rename(columns={0: ''}, inplace=True)

        # Show table
        print(f"\n{tabulate(account_df, headers='keys', tablefmt='psql')}")

        return



    '''
    =========================================================================
    * show_active_trades()                                                  *
    =========================================================================
    * This function will show active trades in webull trading account.      *
    *                                                                       *
    *   INPUT:                                                              *
    *         trades (dict) - Active trades in trading account.             *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def show_active_trades(self, trades={}):

        # If no active trade data provided
        if not trades:
            logging.warning(f"[{self._bot_name}] No active trade data to display!")
            return

        # If paper trading
        if self._paper_trading:
            # Create table
            paper_trades_df = pd.DataFrame.from_dict(trades)
            paper_trades_df.set_index("TradeID", inplace=True)

            # Show table            
            print("\n> > > ACTIVE PAPER TRADES TABLE < < <")
            print(f"{tabulate(paper_trades_df, headers='keys', tablefmt='psql')}", end='\n')

        # Else live trading
        else:
            # Create table
            trades_df = pd.DataFrame.from_dict(trades)
            trades_df.set_index("OptionID", inplace=True)

            # Show table
            print("\n> > > ACTIVE TRADES TABLE < < <")
            print(f"{tabulate(trades_df.iloc[:, :-1], headers='keys', tablefmt='psql')}", end='\n')
            
        return



    '''
    =========================================================================
    * show_active_orders()                                                  *
    =========================================================================
    * This function will show active orders in webull account.              *
    *                                                                       *
    *   INPUT:                                                              *
    *        orders (dict) - Active orders in trading account.              *
    *                                                                       *
    *   OUPUT:                                                              *
    *        None                                                           *
    =========================================================================
    '''
    def show_active_orders(self, orders={}):

        # If no active order data provided
        if not orders:
            logging.warning(f"[{self._bot_name}] No active order data to display!")
            return

        # If paper trading
        if self._paper_trading:
            # Create table
            paper_orders_df = pd.DataFrame.from_dict(orders)
            paper_orders_df.set_index("OrderID", inplace=True)

            # Show table            
            print("\n> > > ACTIVE PAPER ORDERS TABLE < < <")
            print(f"{tabulate(paper_orders_df.iloc[:, :-1], headers='keys', tablefmt='psql')}", end='\n')

        # Else live trading
        else:
            # Create table
            orders_df = pd.DataFrame.from_dict(orders)
            orders_df.set_index("OrderID", inplace=True)

            # Show table
            print("\n> > > ACTIVE ORDERS TABLE < < <")
            print(f"{tabulate(orders_df.iloc[:, :-1], headers='keys', tablefmt='psql')}", end='\n')

        return



    '''
    =========================================================================
    * load_stop_loss_tracker()                                              *
    =========================================================================
    * This function will load the stop loss tracker list for Webull paper   *
    * trading.                                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''

    def load_stop_loss_tracker(self):
        # Initialize stop loss tracker filename
        stop_loss_tracker_file = f"{glob.TRACKER_DIR}paper_stop_loss_tracker{glob.TRACKER_FILE_TYPE}"

        # If stop loss tracker file found
        if os.path.exists(stop_loss_tracker_file):

            # Open file for reading
            with open(stop_loss_tracker_file, "rb") as file:
                try:
                    # Load stop loss tracker contents
                    self._stop_loss_tracker = pickle.load(file)

                    # If debugging enabled
                    if self._debug:
                        logging.info(f"[{self._bot_name}] (DEBUG) Stop loss tracker loaded: {self._stop_loss_tracker}")

                # *** Pickle Error ***
                except (pickle.PickleError, pickle.UnpicklingError):
                    logging.warning(f"[{self._bot_name}] Unable to extract stop loss tracker values from file!")

                # *** Unknown Error ***
                except Exception:
                    logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

        # Else stop loss tracker file not found
        else:
            logging.warning(f"[{self._bot_name}] Could not find stop loss tracker file!")

        return



    '''
    =========================================================================
    * save_stop_loss_tracker()                                              *
    =========================================================================
    * This function will save the stop loss tracker list for Webull paper   *
    * trading.                                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def save_stop_loss_tracker(self):
        # Initialize stop loss tracker filename
        stop_loss_tracker_file = f"{glob.TRACKER_DIR}paper_stop_loss_tracker{glob.TRACKER_FILE_TYPE}"

        # Open stop loss tracker file for writing
        with open(stop_loss_tracker_file, "wb") as file:
            try:
                # Write contents of trade tracker list to trade tracker file
                pickle.dump(self._stop_loss_tracker, file)

                logging.info(f"[{self._bot_name}] Stop loss tracker has been saved!")
            
            # *** Pickle Error ***
            except (pickle.PickleError, pickle.UnpicklingError):
                logging.warning(f"[{self._bot_name}] Unable to save trade tracker values to file!")

            # *** Unknown Error ***
            except Exception:
                logging.error(f"[{self._bot_name}] Unknown error occurred!", exc_info=True)

        return



    '''
    =========================================================================
    * is_logged_in()                                                        *
    =========================================================================
    * This function will return the login status of webull bot.             *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         logged_in (bool) - Webull bot login status.                   *
    =========================================================================
    '''
    def is_logged_in(self):
        return self._logged_in



    '''
    =========================================================================
    * is_paper_trading()                                                    *
    =========================================================================
    * This function will return the paper trading status of webull bot.     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         paper_trading (bool) - Webull bot paper trading status.       *
    =========================================================================
    '''
    def is_paper_trading(self):
        return self._paper_trading
