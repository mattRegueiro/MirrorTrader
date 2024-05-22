'''
=========================================================================
* MirrorTraderMain.py                                                   *
=========================================================================
* The main program execution file for Mirror Trader.                    *
=========================================================================
'''
import logging
import datetime as dt
import pathlib as path

from source.mirror_trader.mt_discord import DiscordBot
from source.mirror_trader.mt_sms import SMSBot
from source.mirror_trader.mt_webull import WebullBot

from source.mirror_trader import mt_globals as g
from source.mirror_trader import mt_misc as m


'''
=========================================================================
* execute()                                                             *
=========================================================================
* This function executes the Mirror Trader program.                     *
*                                                                       *
*   INPUT:                                                              *
*                 config (str) - The name of the input config file.     *
*                 debug (bool) - Mirror Trader Debug Mode.              *
*                   dev (bool) - Mirror Trader Developer Mode.          *
*                                                                       *
*   OUPUT:                                                              *
*         None                                                          *
=========================================================================
'''
def execute(config: str="default.config", debug: bool=False, dev: bool=False) -> None:

    # =======================================
    #   S E T U P
    # =======================================
    m.display_banner()                               # Display program banner
    bot_name = path.Path(__file__).stem                 # Initialize bot name
    m.setup_logger(debug=dev)                        # Initialize program logger

    logging.info(f"++ [{bot_name}] Beginning Mirror Trader execution. . . ")

    # Check for day of week, market holiday, and network connection
    weekend         = m.is_weekend()
    holiday         = m.is_market_holiday() if not weekend else False
    net_connected   = m.is_network_connected() if (not weekend) and (not holiday) else False
 
    # If no network connection or weekend or market holiday and not in developer mode
    if ((not net_connected) or (weekend) or (holiday)) and (not dev):
        logging.info(f"++ [{bot_name}] Ending MirrorTrader execution. . . ")
        return

    # =======================================
    #   R E A D   C O N F I G   D A T A
    # =======================================
    # If unencrypted config file
    if config.endswith(g.DECRYPT_EXT):
        if dev:
            success, discord, webull, sms, trading = m.read_config(config_file=config)
        else:
            logging.error(f"++ [{bot_name}] Profile file needs to be encrypted! Run Cryptor to encrypt profile file.")
            return

    # Else if encrypted config file
    elif config.endswith(g.ENCRYPT_EXT):
        success, discord, webull, sms, trading = m.read_encrypt_config(encrypt_config_file=config)

    # Else invalid config file
    else:
        logging.error(f"++ [{bot_name}] Invalid file extension! Need '.config' or '.aes' file types.")
        return

    # If unable to unpack profile config parameters
    if not success:
        logging.info(f"++ [{bot_name}] Ending MirrorTrader execution. . . ")
        return


    # =======================================
    #   B O T   S E T U P
    # =======================================
    # Setup Discord bot
    D_bot = DiscordBot(invest_percent=trading['percentInvst'],
                       SL_percent=trading['defaultSL'],
                       paper=webull['paperTrade'],
                       debug=debug,
                       dev=dev)

    # Setup Webull bot
    W_bot = WebullBot(device_id=webull["deviceID"],
                      max_price_diff=trading['maxPriceDiff'],
                      SL_percent= trading['defaultSL'],
                      paper_trading=webull['paperTrade'],
                      debug=debug,
                      dev=dev)

    # Setup SMS bot
    S_bot = SMSBot(debug=debug, dev=dev)

    # Login to Discord and Webull accounts
    D_bot.login(username=discord['email'], password=discord['password'])
    W_bot.login(username=webull['email'], password=webull['password'], trade_pin=webull['tradePin'])

    # If SMS bot enabled
    if sms['enable']:
        S_bot.login(username=sms['email'], password=sms['password'], phone_number=sms['phone'], carrier=sms['carrier'])



    # =======================================
    #   P R O G R A M   E X E C
    # =======================================
    # If sucessful login status
    if D_bot.is_logged_in() and W_bot.is_logged_in():

        D_bot.find_guild(guild=discord['server'])           # Access Discord guild/server

        # If Discord guild/server accessed
        if D_bot.is_guild_accessed():

            D_bot.find_channel(channels=discord['channels'])     # Search for channel(s) within accessed guild

            # If Discord channel(s) accessed
            if D_bot.is_channel_accessed():

                # If developer mode not enabled
                if not dev:
                    
                    # If current time is earlier than market open time
                    if dt.datetime.now().time() < g.MARKET_OPEN_TIME:

                        # Wait until US stock market opens
                        logging.info(f"[{bot_name}] Active search for trades will begin at {g.MARKET_OPEN_TIME.strftime(g.TIME_FORMAT_12HR)}. . .")
                        m.wait_till_market_open()

                # If program shutdown event not set or developer mode enabled
                if (not g.PROGRAM_SHUTDOWN.is_set()) or (dev):

                    g.MARKET_OPEN.set()          # Set market open event

                    D_bot.run_channels_thread()     # Start Discord channel thread
                    W_bot.run_manager_threads()     # Start Webull manager threads

                    # If successful SMS login
                    if S_bot.is_logged_in():
                        S_bot.run_listen_thread()   # Start SMS listen thread

                try:
                    while ((dt.datetime.now().time() < g.MARKET_CLOSE_TIME) or (dev)) and (not g.PROGRAM_SHUTDOWN.is_set()):

                        # If program queue is not empty
                        if not g.PROGRAM_QUEUE.empty():

                            # Get the item from the queue and determine the bot that the item belongs to
                            queue_item = g.PROGRAM_QUEUE.get()
                            bot = next(iter(queue_item))

                            # If debugging enabled
                            if debug:
                                logging.info(f"[{bot_name}] (DEBUG) Program Queue Item: {bot} | {queue_item[bot]}\n")



                            # =======================================
                            #   S M S   Q U E U E   I T E M
                            # =======================================
                            if (S_bot.is_logged_in()) and (bot == S_bot.get_name()):

                                # Acknowledge message
                                logging.info(f"[{bot_name}] Received incoming SMS message at {dt.datetime.today().time().strftime(g.TIME_FORMAT_12HR)}")
                                S_bot.sms_send_confirmation_message()

                                # Get the SMS message
                                sms_msg = queue_item[bot]
                                
                                # If SMS message received is shutdown command
                                if sms_msg.upper() in g.SMS_SHUTDOWN_COMMANDS:

                                    # Set program shutdown event
                                    if not g.PROGRAM_SHUTDOWN.is_set():
                                        g.PROGRAM_SHUTDOWN.set()

                                # Else invalid command
                                else:
                                    S_bot.sms_send_error_message(invalid_cmd=True)



                            # =======================================
                            #   A L E R T   Q U E U E   I T E M
                            # =======================================
                            if (bot in discord['channels']) or (dev):

                                # Extract the trade alert from the queue item
                                trade_alert = queue_item[bot]

                                # If developer mode and "End_Debug" keyword received
                                if (dev) and (trade_alert == "END_DEBUG"):

                                    # Set program shutdown event
                                    if not g.PROGRAM_SHUTDOWN.is_set():
                                        g.PROGRAM_SHUTDOWN.set()

                                # Else not in developer mode
                                else:

                                    # If live trading
                                    if not W_bot.is_paper_trading():

                                        if trade_alert['Signal'] == "BTO":      # BUY TO OPEN
                                            # Place option BUY order
                                            W_bot.place_order(action="BUY",
                                                              ticker=trade_alert['Ticker'],
                                                              strike_price=trade_alert['Strike'],
                                                              direction=trade_alert['Direction'],
                                                              exp_date=trade_alert['ExpDate'],
                                                              price=trade_alert['Price'],
                                                              percent=trade_alert['Info']['Percent'],
                                                              stop_loss=trade_alert['StopLoss'])

                                        if trade_alert['Signal'] == "STC":      # SELL TO CLOSE
                                            # Place option SELL order
                                            W_bot.place_order(action="SELL",
                                                              ticker=trade_alert['Ticker'],
                                                              strike_price=trade_alert['Strike'],
                                                              direction=trade_alert['Direction'],
                                                              exp_date=trade_alert['ExpDate'],
                                                              price=trade_alert['Price'],
                                                              percent=trade_alert['Info']['Percent'],
                                                              order_type="MKT")

                                    # Else paper trading
                                    else:

                                        if trade_alert['Signal'] == "BTO":      # BUY TO OPEN
                                            
                                            if trade_alert['Direction'] == 'call':
                                                # Place paper BUY order
                                                W_bot.place_paper_order(action="BUY",
                                                                        ticker=trade_alert['Ticker'],
                                                                        percent=trade_alert['Info']['Percent'])

                                            if trade_alert['Direction'] == 'put':
                                                # Place paper SELL order
                                                W_bot.place_paper_order(action="SELL",
                                                                        ticker=trade_alert['Ticker'],
                                                                        percent=trade_alert['Info']['Percent'],
                                                                        short=True)

                                        if trade_alert['Signal'] == "STC":      # SELL TO CLOSE

                                            if trade_alert['Direction'] == 'call':
                                                # Place paper SELL order
                                                W_bot.place_paper_order(action="SELL",
                                                                        ticker=trade_alert['Ticker'],
                                                                        percent=trade_alert['Info']['Percent'],
                                                                        order_type="MKT")

                                            if trade_alert['Direction'] == 'put':
                                                # Place paper BUY order
                                                W_bot.place_paper_order(action="BUY",
                                                                        ticker=trade_alert['Ticker'],
                                                                        percent=trade_alert['Info']['Percent'],
                                                                        short=True,
                                                                        order_type="MKT")

                            # Mark program queue task as complete
                            g.PROGRAM_QUEUE.task_done()

                # *** Keyboard Exit ***
                except KeyboardInterrupt:
                    pass



                # =======================================
                #   C L E A N U P
                # =======================================
                # Set market close
                g.MARKET_OPEN.clear()
                
                # # Set program shutdown event
                # if not g.PROGRAM_SHUTDOWN.is_set():
                #     g.PROGRAM_SHUTDOWN.set()

                # Wait for all running threads to end
                for thread in g.ACTIVE_THREADS:
                    logging.info(f"[{bot_name}] Closing thread {thread.getName()}. . .")
                    thread.join()

                # Logout of Discord and Webull accounts
                D_bot.logout()
                W_bot.logout()

                # If SMS logged in
                if S_bot.is_logged_in():
                    S_bot.logout()
    
    logging.info(f"[{bot_name}] End of Mirror Trader program reached!")

    return