'''
=============================================================================
* mt_endpoints.py                                                           *
=============================================================================
* This file contains endpoint classes for Discord and Webull bots. Endpoint *
* classes contain various http API calls that are used by the bots when     *
* sending API requests.                                                     *
=============================================================================
'''
from source.mirror_trader import mt_globals as glob

###################################################################
#   D I S C O R D   E N D P O I N T S   C L A S S                 #
###################################################################
class DiscordEndpoints:
    def __init__(self):
        self.base_api_url = 'https://discord.com/api/v9'
        self.base_captcha_url = 'https://hcaptcha.com'

    def captcha_checksite(self, host='', sitekey='', sc=1, swa=1):
        return f"{self.base_captcha_url}/checksiteconfig?host={host}&sitekey={sitekey}&sc={sc}&swa={swa}"

    def captcha_get(self, sitekey=''):
        return f"{self.base_captcha_url}/getcaptcha?s={sitekey}"

    def account(self, user_id=''):
        if user_id:
            return f"{self.base_api_url}/users/{user_id}"
        else:
            return f"{self.base_api_url}/users/@me"

    def settings(self):
        return f"{self.base_api_url}/users/@me/settings"

    def profile(self, user_id='', with_mutual_guilds=False):
        return f"{self.account(user_id=user_id)}/profile?with_mutual_guilds={with_mutual_guilds}"

    def location_metadata(self):
        return f"{self.base_api_url}/auth/location-metadata"

    def login(self):
        return f"{self.base_api_url}/auth/login"

    def logout(self):
        return f"{self.base_api_url}/auth/logout"

    def guilds(self):
        return f"{self.base_api_url}/users/@me/guilds"

    def guild(self, guild_id=''):
        return f"{self.base_api_url}/guilds/{guild_id}"

    def guild_settings(self, guild_id=''):
        return f"{self.account()}/guilds/{guild_id}/settings"

    def channels(self, guild_id=''):
        return f"{self.base_api_url}/guilds/{guild_id}/channels"

    def channel(self, channel_id=''):
        return f"{self.base_api_url}/channels/{channel_id}"

    def channel_settings(self, channel_id=''):
        return f"{self.base_api_url}/channels/{channel_id}/settings"

    def library(self):
        return f"{self.base_api_url}/users/@me/library"

    def users(self):
        return f"{self.base_api_url}/users/@me/affinities/users"

    def channel_messages(self, channel_id='', message_limit=glob.DISCORD_CHANNEL_MESSAGE_LIMIT):
        return f"{self.base_api_url}/channels/{channel_id}/messages?limit={message_limit}"
