'''
=============================================================================
* mt_discord.py                                                             *
=============================================================================
* This file contains the DiscordBot class and all functions associated with *
* accessing active Discord trading servers and channels to listen for and   *
* extract option trade alerts.                                              *
=============================================================================
'''
import re
import getpass
import logging
import requests
import pandas as pd

from tabulate import tabulate
from source.mirror_trader import mt_globals as glob
from source.mirror_trader.mt_alerts import TradeAlerts
from source.mirror_trader.mt_endpoints import DiscordEndpoints



###################################################################
#   D I S C O R D B O T   C L A S S                               #
###################################################################
class DiscordBot:
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes all appropriate flags, lists, and tables    *
    * used to handle the processing of option trade alerts. Tables and      *
    * lists are created to support different trading servers and channels   *
    * hosted on the Discord website.                                        *
    *                                                                       *
    *   INPUT:                                                              *
    *   invest_percent (float) - Percentage of account to invest in.        *
    *       SL_percent (float) - Default stop loss percentage.              *
    *             paper (bool) - Paper trade status for paper trade logic.  *
    *             debug (bool) - Debug status to view trade alert details.  *
    *               dev (bool) - Developer mode status.                     *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self, invest_percent: float=0.0, SL_percent: float=0.0, 
                    paper: bool=False, debug: bool=False, dev: bool=False):
        # Correct input arguments if None
        invest_percent = invest_percent or 0.0
        SL_percent = SL_percent or 0.0
        paper = paper or False

        # Initialize header for Discord API requests
        self._headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json",
            "platform": "web",
            "ver": "3.22.20",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36",
        }

        # Initialize Discord API urls and authorization token
        self._URLS              = DiscordEndpoints()            # DiscordEndpoints class containing Discord API URLS
        self._authorization     = "undefined"                   # Discord API authorization token

        # Set bot name and paper, debug, dev, and logged in statuses
        self._bot_name          = str(self.__class__.__name__)  # Bot name (DiscordBot)
        self._paper             = paper                         # Discord paper trade logic status
        self._debug             = debug                         # Discord debug status
        self._dev               = dev                           # Discord developer mode status
        self._logged_in         = False                         # Discord login status

        # Set account investment and default stop loss percentages
        self._invest_percent    = invest_percent                # Percentage of account to invest in trade
        self._default_SL        = SL_percent                    # Default stop loss percentage

        # Create containers to store affiliated Discord guilds and channels
        self._guilds            = {}                            # Dictionary containing guild name and id
        self._channels          = {}                            # Dictionary containing channel name and id for a guild
        
        # Initialize guild and channel accessed structures
        self._guild_accessed    = {                             # Dictionary containing access status, name, and ID of accessed discord guild
            "Accessed": False,
            "Name": "",
            "Id": ""
        }
        self._channel_accessed  = {                             # Dictionary containing access status, name, and ID of accessed discord channel
            "Accessed": False,
            "Name": "",
            "Id": ""
        }
        self._channels_selected = []                            # List containing all channels accessed within an selected Discord guild
        
        return



    '''
    =========================================================================
    * build_req_headers()                                                   *
    =========================================================================
    * This function will build the default set of header parameters used to *
    * send a Discord API request.                                           *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         headers (dict) - Dictionary of header parameters.             *
    =========================================================================
    '''
    def build_req_headers(self):
        # Re-initialize headers
        headers = self._headers

        # Set Discord authorization token
        headers["Authorization"] = self._authorization

        return headers



    '''
    =========================================================================
    * login()                                                               *
    =========================================================================
    * This function will login to a user's Discord account using their      *
    * login credentials.                                                    *
    *                                                                       *
    *   INPUT:                                                              *
    *          username (str) - Discord login username or phone number.     *
    *          password (str) - Discord login password.                     *
    *         undelete (bool) - ???                                         *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def login(self, username="", password="", undelete=False):
        # Initialize number of login attempts made
        login_attempts = 0

        # Loop while not logged in and max number of login attempts has not been reached
        while (not self._logged_in) and (login_attempts < glob.MAX_DISCORD_LOGIN_ATTEMPTS):

            # If no username or password provided or invalid login
            if (not username) or (not password) or (login_attempts > 0):
                logging.warning(f"[{self._bot_name}] Invalid Discord username or password! Please try again.")
                input("Press <enter> to continue. . .")

                # Enter email/phone and password
                username = input(f"[{self._bot_name}] Enter Discord Email or Phone Number: ")
                password = getpass.getpass(f"[{self._bot_name}] Enter Discord Password: ")

            # Pack data to be sent to Discord login API
            data = {
                "login"             : username,
                "password"          : password,
                "undelete"          : undelete,
                "captcha_key"       : None,
                "gift_code_sku_id"  : None,
                "login_source"      : None
            }

            # Send login request
            headers = self.build_req_headers()
            response = requests.post(self._URLS.login(), json=data, headers=headers)
            result = response.json()

            # If successful request (status code == 200)
            if response.status_code == 200:
                logging.info(f"[{self._bot_name}] Login successful!")

                # Set Discord authorization token and logged in status
                self._authorization = result['token']
                self._logged_in = True
                    
                # Build dictionary of affilliated guilds
                self.get_guilds()

                return
            
            # Else unsuccessful request
            else:

                # If unsuccessful login attempt
                if "errors" in result:

                    # Get error code and error message
                    error = result['errors']['login']['_errors'][0]['code']
                    error_msg = result['errors']['login']['_errors'][0]['message']

                    # Display error message
                    logging.warning(f"[{self._bot_name}] {error.upper()}: {error_msg}")

                    # Increment login attempts tried
                    login_attempts += 1
                    logging.warning(f"[{self._bot_name}] ({login_attempts}/{glob.MAX_DISCORD_LOGIN_ATTEMPTS}) login attempts tried.")

                # TODO: Else Captch Handling
                else:
                    logging.warning(f"[{self._bot_name}] CAPTCHA_INVALID_LOGIN: Username or password is incorrect!")

                    # Increment login attempts tried
                    login_attempts += 1
                    logging.warning(f"[{self._bot_name}] ({login_attempts}/{glob.MAX_DISCORD_LOGIN_ATTEMPTS}) login attempts tried.")

        # If maximum login attempts have been reached
        if login_attempts == glob.MAX_DISCORD_LOGIN_ATTEMPTS:
            logging.error(f"[{self._bot_name}] Max number of login attempts have been reached. . . stopping login execution.")

        return



    '''
    =========================================================================
    * logout()                                                              *
    =========================================================================
    * This function will logout of a user's Discord account.                *
    *                                                                       *
    *   INPUT:                                                              *
    *              provider (str) - ???                                     *
    *         voip_provider (str) - ???                                     *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def logout(self, provider='', voip_provider=''):
        # If logged in
        if self._logged_in:
            
            # Set provider
            if not provider:
                provider = None
            
            # Set VOIP provider
            if not voip_provider:
                voip_provider = None

            # Pack data to be sent to Discord logout API
            data = {
                'provider'      : provider,
                'voip_provider' : voip_provider
            }

            # Send logout request
            headers = self.build_req_headers()
            response = requests.post(self._URLS.logout(), json=data, headers=headers)

            # If successful logout
            if response.status_code == 204:
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



    #####################################
    #   G U I L D   F U N C T I O N S   #
    #####################################
    '''
    =========================================================================
    * get_guilds()                                                          *
    =========================================================================
    * This function will build a dictionary containing all user affiliated  *
    * Discord guilds.                                                       *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_guilds(self):
        # If logged in
        if self._logged_in:

            # Request list of discord guilds that the user is affiliated with
            headers = self.build_req_headers()
            response = requests.get(self._URLS.guilds(), headers=headers)

            # If successful request (status code == 200)
            if response.status_code == 200:

                # Get list of guilds
                guilds = response.json()

                # If affiliated guilds found
                if guilds:

                    # Build the dictionary of guild ids
                    self._guilds = {guild['name']: guild['id'] for guild in guilds if ('name' in guild) and ('id' in guild)}

                # Else no affiliated guilds found
                else:
                    logging.warning(f"[{self._bot_name}] No affiliated guilds found!")

            # Else unsuccessful request
            else:
                logging.error(f"[{self._bot_name}] Unable to request for affiliated guilds!")

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * find_guild()                                                          *
    =========================================================================
    * This function will find a specified discord guild.                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         guild (str) - The name of the discord guild being accessed.   *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def find_guild(self, guild=''):
        # If logged in
        if self._logged_in:

            # Initialize the number of attempts that will be made to find a guild
            search_attempts = 0

            # Loop while guild has not been accessed and max search attempts has not beed reached
            while (not self._guild_accessed["Accessed"]) and (search_attempts < glob.MAX_DISCORD_SEARCH_ATTEMPTS):
                
                # If no guild name provided or guild name not found in affiliated guilds dictionary
                if (not guild) or (guild not in self._guilds):
                    logging.warning(f"[{self._bot_name}] Invalid Discord guild provided! Please try again.")
                    input("Press <enter> to continue. . .")

                    # Show available guilds to access and prompt for guild selection
                    self.show_affiliated_guilds()
                    guild = input(f"[{self._bot_name}] Enter Discord Guild Name: ")

                # Access guild
                self.access_guild(guild)

                # If Discord guild not found, increment number of search attempts tried
                if not self._guild_accessed["Accessed"]:
                    search_attempts += 1

            # If maximum search attempts tried have been reached
            if search_attempts == glob.MAX_DISCORD_SEARCH_ATTEMPTS:
                logging.error(f"[{self._bot_name}] Max number of guild search attempts have been reached. . . stopping execution.")

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * access_guild()                                                        *
    =========================================================================
    * This function will access a specified Discord guild if found in the   * 
    * constructed guilds table.                                             *
    *                                                                       *
    *   INPUT:                                                              *
    *         guild_name (str) - The name of the discord guild being        *
    *                             accessed.                                 *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def access_guild(self, guild_name=''):
        # If logged in 
        if self._logged_in:

            # If guild found
            if guild_name in self._guilds:
                logging.info(f"[{self._bot_name}] Guild '{guild_name}' found!")

                # Set guild accessed
                self._guild_accessed = {'Accessed'  : True,
                                        'Name'      : guild_name,
                                        'Id'        : self._guilds[guild_name]}

                # Build dictionary of guild channels
                self.get_channels()
            
            # Guild not found
            else:
                logging.warning(f'[{self._bot_name}] Could not find guild: {guild_name}')
        
        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * get_guild_info()                                                      *
    =========================================================================
    * This function will show all available information for the currently   *
    * accessed Discord guild.                                               *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_guild_info(self):
        # If logged in
        if self._logged_in:

            # If guild has been accessed
            if self._guild_accessed["Accessed"]:

                # Initialize guild info dictionary
                guild_info = {}

                # Request information about accessed guild
                headers = self.build_req_headers()
                response = requests.get(self._URLS.guild(guild_id=self._guild_accessed['Id']), headers=headers)

                # If successful request (status code == 200)
                if (response.status_code == 200):

                    # Get guild information
                    result = response.json()

                    # Populate guild information dictionary
                    guild_info[result['name']] = {
                        "Guild Id": result['id'],
                        "Region": result['region'],
                        "Verification Level": result['verification_level'],
                        "MFA Level": result['mfa_level'],
                        "Max Members": result['max_members'],
                        "NSFW": result['nsfw']
                    }

                    # Convert guild info dictionary to dataframe table
                    info_df = pd.DataFrame.from_dict(guild_info, orient='index')
                    info_df.index.name = "DISCORD GUILD INFO"
                    info_df.rename(columns={0:''}, inplace=True)

                    # Show table
                    print(f"\n{tabulate(info_df, headers='keys', tablefmt='psql')}")

                # Else unsuccessful request
                else:
                    logging.error(f"[{self._bot_name}] Unable to request for accessed guild information!")

            # Else guild has not been accessed
            else:
                logging.warning(f"[{self._bot_name}] Need to access a guild first!")
        
        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * show_affiliated_guilds()                                              *
    =========================================================================
    * This function will show all affiliated guilds within a user's discord *
    * account.                                                              *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def show_affiliated_guilds(self):
        # If logged in
        if self._logged_in:

            # If there are affiliated guilds to show
            if self._guilds:

                # Convert affiliated guilds dictionary to dataframe table
                guilds_df = pd.DataFrame.from_dict(self._guilds, orient='index')
                guilds_df.index.name = "AVAILABLE DISCORD GUILDS"
                guilds_df.rename(columns={0:''}, inplace=True)

                # Show table
                print(f"\n{tabulate(guilds_df, headers='keys', tablefmt='psql')}")
            
            # Else there are no affiliated guilds to show
            else:
                logging.warning(f"[{self._bot_name}] No affiliated guilds to display!")

        # Else not logged in 
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    #########################################
    #   C H A N N E L   F U N C T I O N S   #
    #########################################
    '''
    =========================================================================
    * get_channels()                                                        *
    =========================================================================
    * This function will build a dictionary containing all channels found   *
    * within an accessed Discord guild.                                     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_channels(self):
        # If logged in
        if self._logged_in:

            # If guild accessed
            if self._guild_accessed:

                # Request list of channels within a discord guild that the user is affiliated with
                headers = self.build_req_headers()
                response = requests.get(self._URLS.channels(guild_id=self._guild_accessed['Id']), headers=headers)

                # If successful request (status code == 200)
                if response.status_code == 200:

                    # Get list of channels
                    channels = response.json()

                    # If guild channels found
                    if channels:

                        # Build the dictionary of channel ids
                        self._channels = {glob.EMOJI_FILTER.sub("", channel["name"]): channel['id'] for channel in channels if (channel["type"] == 0) and (channel["name"] not in self._channels)}

                    # Else no guild channels found
                    else:
                        logging.warning(f"[{self._bot_name}] No channels found in {self._guild_accessed['Name']}!")

                # Else unsuccessful request
                else:
                    logging.error(f"[{self._bot_name}] Unable to request list of accessed guild channels!")

            # Else guild not accessed
            else:
                logging.warning(f"[{self._bot_name}] Need to access a guild first!")
        
        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * run_channels_thread()                                                 *
    =========================================================================
    * This function will start a thread for each channel selected to search *
    * for option trades.                                                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def run_channels_thread(self):
        # If logged in     
        if self._logged_in:

            # If guild accessed
            if self._guild_accessed["Accessed"]:
                
                # If channels selected
                if self._channels_selected:

                    # Setup thread to search for trade alerts in selected channel
                    channel_thread = TradeAlerts(headers=self._headers, 
                                                 channel=self._channels_selected,
                                                 invest_percent=self._invest_percent,
                                                 SL_percent=self._default_SL,
                                                 paper=self._paper, 
                                                 debug=self._debug,
                                                 dev = self._dev)

                    # If channel thread valid
                    if channel_thread:

                        # Start thread and add to active threads list
                        channel_thread.start()
                        glob.ACTIVE_THREADS.append(channel_thread)

                # Else channels not selected
                else:
                    logging.error(f"[{self._bot_name}] Could not access any channel from {self._guild_accessed['name']}!")

            # Else guild not accessed
            else:
                logging.warning(f"[{self._bot_name}] Need to access a guild first!")

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * find_channel()                                                        *
    =========================================================================
    * This function will find a specified channel within a selected discord * 
    * guild.                                                                *
    *                                                                       *
    *   INPUT:                                                              *
    *         channel (str) - The name of the discord channel being         * 
    *                         accessed.                                     *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def find_channel(self, channels=[]):
        # Initialize the number of attempts that will be made to find a channel
        search_attempts = 0

        # Loop while channels have not been selected and max search attempts has not beed reached
        while (not self._channels_selected) and (search_attempts < glob.MAX_DISCORD_SEARCH_ATTEMPTS):
            
            # If no channels have been provided
            if not channels:
                logging.warning(f"[{self._bot_name}] No channels provided! Please select a channel(s) from {self._guild_accessed['Name']}")
                input("Press <enter> to continue. . .")

                # Show available channels to access and prompt for channel selection
                self.show_affiliated_channels()
                print("!!! Use ',', ' ', or '/' to separate channel names !!!")
                channel_input = input(f"[{self._bot_name}] Enter {self._guild_accessed['Name']} channel name: ")
                channels = list(filter(None, re.split(',|\s|\/', channel_input)))

            # Loop through each channel selected
            for channel in channels:

                # Access channel
                self.access_channel(channel)

                # If channel accessed
                if self._channel_accessed["Accessed"]:

                    # Add channel accessed to channels selected list
                    self._channels_selected.append(self._channel_accessed)

            # If channels selected list is empty
            if not self._channels_selected:
                search_attempts += 1

        # If maximum search attempts tried have been reached
        if search_attempts == glob.MAX_DISCORD_SEARCH_ATTEMPTS:
            logging.error(f"[{self._bot_name}] Max number of channel search attempts have been reached. . . stopping execution.")

        return



    '''
    =========================================================================
    * access_channel()                                                      *
    =========================================================================
    * This function will access a specified Discord guild channel if found  *
    * in the constructed channels table.                                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         channel_name (str)  - The name of the discord channel being   *
    *                               accessed by the user.                   *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def access_channel(self, channel_name=''):
        # If logged in
        if self._logged_in:

            # If guild accessed
            if self._guild_accessed:

                # If channel found
                if channel_name in self._channels:
                    logging.info(f"[{self._bot_name}] Channel '{channel_name}' found!")

                    # Set channel accessed
                    self._channel_accessed = {'Accessed'  : True,
                                              'Name'      : channel_name,
                                              'Id'        : self._channels[channel_name]}

                # Else channel not found
                else:
                    
                    # If no channel name provided
                    if not channel_name:
                        logging.error(f"[{self._bot_name}] Cannot access channel without channel name!")
                
                    # Else channel name not in channels dictionary
                    else:
                        logging.warning(f"[{self._bot_name}] Could not find channel {channel_name} in {self._guild_accessed['Name']}!")

            # Else guild not accessed
            else:
                logging.warning(f"[{self._bot_name}] Need to access a guild first!")

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * get_channel_info()                                                    *
    =========================================================================
    * This function will show all available information for the currently   *
    * accessed Discord guild channel(s).                                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def get_channel_info(self):
        # If logged in
        if self._logged_in:

            # If guild accessed
            if self._guild_accessed['Accessed']:

                # If channel(s) have been selected
                if self._channels_selected:

                    # Initialize channel info dictionary
                    channel_info = {}

                    # Loop through selected channels
                    for channel in self._channels_selected:

                        # Request information about selected channel
                        headers = self.build_req_headers()
                        response = requests.get(self._URLS.channel(channel_id=channel['Id']), headers=headers)

                        # If successful request (status code == 200)
                        if (response.status_code == 200):

                            # Get channel information
                            result = response.json()

                            # Populate channel info dictionary with channel information
                            channel_info[glob.EMOJI_FILTER.sub('',result['name'])] = {
                                "Channel Id": result['id'],
                                "Guild Id": result['guild_id'],
                                "Type": result['type'],
                                "Position": result['position'],
                                "NSFW": result['nsfw']
                            }

                        # Else unsuccessful request
                        else:
                            logging.error(f"[{self._bot_name}] Unable to request for '{channel}' channel information!")

                    # If there is channel information to show
                    if channel_info:

                        # Convert channel info dictionary to dataframe table
                        info_df = pd.DataFrame.from_dict(channel_info, orient='index')
                        info_df.index.name = f"{self._guild_accessed['Name']} CHANNELS"
                        info_df.rename(columns={0:''}, inplace=True)

                        # Show table
                        print(f"\n{tabulate(info_df, headers='keys', tablefmt='psql')}\n")

                    # Else there is no channel information to show
                    else:
                        logging.warning(f"[{self._bot_name}] No channel information to show!")

                # Else no channels have been selected
                else:
                    logging.warning(f"[{self._bot_name}] Need to access a channel first!")

            # Else guild not accessed
            else:
                logging.warning(f"[{self._bot_name}] Need to access a guild first!")
        
        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * show_affiliated_channels()                                            *
    =========================================================================
    * This function will show all affiliated channels within a selected     *
    * discord guild.                                                        *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def show_affiliated_channels(self):
        # If logged in
        if self._logged_in:

            # If guild accessed
            if self._guild_accessed['Accessed']:

                # If there are affiliated channels to show
                if self._channels:

                    # Convert affiliated channels dictionary to dataframe table
                    channels_df = pd.DataFrame.from_dict(self._channels, orient='index')
                    channels_df.index.name = f"AVAILABLE {self._guild_accessed['Name']} CHANNELS"
                    channels_df.rename(columns={0:''}, inplace=True)

                    # Show table
                    print(f"\n{tabulate(channels_df, headers='keys', tablefmt='psql')}")
                
                # Else no available guild channels to show
                else:
                    logging.warning(f"[{self._bot_name}] No guild channels to show!")

            # Else guild not accessed
            else:
                logging.warning(f"[{self._bot_name}] Need to access a guild first!")
        
        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    ###################################
    #   M I S C   F U N C T I O N S   #
    ###################################
    '''
    =========================================================================
    * is_logged_in()                                                        *
    =========================================================================
    * This function will return the login status of Discord bot.            *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         logged_in (bool) - Discord bot login status.                  *
    =========================================================================
    '''
    def is_logged_in(self):
        return self._logged_in



    '''
    =========================================================================
    * is_guild_accessed()                                                   *
    =========================================================================
    * This function will return the guild accessed status of Discord bot.   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         _guild_accessed["Accessed"] (bool) - Guild accessed status.   *
    =========================================================================
    '''
    def is_guild_accessed(self):
        return self._guild_accessed["Accessed"]



    '''
    =========================================================================
    * is_channel_accessed()                                                 *
    =========================================================================
    * This function will return the channel accessed status of Discord bot. *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         True/False (bool) - Channel(s) accessed status.               *
    =========================================================================
    '''
    def is_channel_accessed(self):
        # If there are valid channels selected
        if len(self._channels_selected) > 0:
            return True

        # Else there are no valid channels selected
        else:
            return False




