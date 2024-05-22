'''
=========================================================================
* mt_sms.py                                                             *
=========================================================================
* This file contains the SMSBot class and all functions associated with *
* sending and receiving SMS messges using Gmail SMTP and IMAP servers.  *
* SMSBot is used as a medium to allow a user to shutdown the Mirror     *
* Trader program if necessary.                                          *
*                                                                       *
* NOTE:                                                                 *
* Users need to enable 2-Factor Authentication and setup an app-        *
* password from their google account in order to use the SMSBot class.  *
* The app-password is used in place of the user's gmail password when   *
* using the SMSBot class and it's functions.                            *
=========================================================================
'''

import os
import time
import email
import logging
import threading
import datetime as dt
import smtplib as smtp
import imapclient as imap
import imapclient.exceptions as imap_exceptions
import source.mirror_trader.mt_globals as glob
import source.mirror_trader.mt_misc as misc

from getpass import getpass
from email.mime.text import MIMEText
from email.message import EmailMessage
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication



class SMSBot():
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes all appropriate variables required to send  *
    * and receive text messages via Gmail SMTP and IMAP servers.            *
    *                                                                       *
    *   INPUT:                                                              *
    *         debug (bool) - Sets SMSBot debug status.                      *
    *           dev (bool) - Sets SMSBot developer mode status.             *
    *         kwargs (str) - Keyword arguments used to either move, delete  *
    *                         or mark emails as read.                       *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self, debug=False, dev=False):
        # Set bot name, logged in status, network connected status, and debug status
        self._bot_name          = str(self.__class__.__name__)  # Set name of the bot (SMSBot)
        self._logged_in         = False                         # Login status flag
        self._network_connected = True                          # Internet connection status
        self._debug             = debug                         # Debug status
        self._dev               = dev                           # Developer mode status

        # Initialize email and password
        self._email             = ""                            # Email login username
        self._password          = ""                            # Email login password

        # Initialize cell phone number, cell phone carrier, and receiver
        self._phone_number      = ""                            # Phone number of message receiver
        self._carrier           = ""                            # Cell phone provider/carrier
        self._receiver          = ""                            # Receiver of SMS messages

        # Initialize SMSBot thread and IMAP (receiver) and SMTP (sender) clients
        self._sms_thread        = None                          # SMSBot thread
        self._imap_client       = None                          # Email IMAP client
        self._smtp_client       = None                          # Email SMTP client

        return



    '''
    =========================================================================
    * run_listen_thread()                                                   *
    =========================================================================
    * This function creates and starts the SMSBot thread to listen for      *
    * incoming SMS messages from a user.                                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def run_listen_thread(self):
        # Create thread to listen for incoming SMS messages
        self._sms_thread = threading.Thread(target=self.wait_for_incoming_messages) # Initialize thread
        self._sms_thread.setName(name=self._bot_name)                               # Set name of thread
        self._sms_thread.setDaemon(daemonic=True)                                   # Set thread as background task

        # Start thread
        self._sms_thread.start()

        # Add thread to the program active threads list
        glob.ACTIVE_THREADS.append(self._sms_thread)

        return

        

    '''
    =========================================================================
    * login()                                                               *
    =========================================================================
    * This function will use a user's login credentials to log into their   *
    * Gmail account.                                                        *
    *                                                                       *
    *   INPUT:                                                              *
    *             username (str) - Gmail email address.                     *
    *             password (str) - Gmail password.                          *
    *         phone_number (str) - Cell phone number.                       *
    *              carrier (str) - Cell phone carrier/provider.             *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def login(self, username='', password='', phone_number='', carrier=''):
        # Initialize and track the number of login attempts made/available
        login_attempts = 0

        # Loop while not logged in and login attempts available and network connection is established
        while (not self._logged_in) and (login_attempts < glob.MAX_SMS_LOGIN_ATTEMPTS) and (self._network_connected): 

            # If no username or password or phone number of carrier provided or invalid login
            if (not username) or (not password) or (not phone_number) or (not carrier) or (login_attempts > 0):

                # Get username, password, phone number, and carrier
                self._email = input(f"[{self._bot_name}] Enter Email: ")
                self._password = getpass(f"[{self._bot_name}] Enter Email Password: ")
                self._phone_number = input(f"[{self._bot_name}] Enter phone number: ")
                self._carrier = input(f"[{self._bot_name}] Enter phone provider/carrier: ")

            # Else username and password and phone number and carrier provided and not invalid login
            else:
                
                # Set username, password, phone number, and carrier
                self._email = username
                self._password = password
                self._phone_number = phone_number
                self._carrier = carrier

            try:
                # Setup IMAP client and login
                self._imap_client = imap.IMAPClient(host=glob.SMS_IMAP_HOST, port=glob.SMS_IMAP_PORT, ssl_context=glob.SMS_SSL)
                self._imap_client.login(username=self._email, password=self._password)

                logging.info(f"[{self._bot_name}] Login Successful!")

                # Set login status to true
                self._logged_in = True

                # Set receiver
                self._receiver = self._phone_number + glob.CARRIERS[self._carrier.lower()]

                # Send SMS startup message to receiver
                self.sms_send_startup_message()

                # If current time is earlier than market open time and developer mode not enabled
                if (dt.datetime.now().time() < glob.MARKET_OPEN_TIME) and (not self._dev):

                    # Execute periodic no-ops to prevent logout
                    self._sms_thread = threading.Thread(target=self.periodic_noop)  # Initialize thread
                    self._sms_thread.setName(name=f"PeriodicNoOp")                  # Set name of thread
                    self._sms_thread.setDaemon(daemonic=True)                       # Set thread as background task

                    # Start thread
                    self._sms_thread.start()


            # *** Invalid Login ***
            except imap_exceptions.LoginError:
                logging.warning(f"[{self._bot_name}] Invalid SMS login credentials!")

                # Increment login attempts
                login_attempts += 1

            # *** IMAP Abort Error ***
            except imap_exceptions.IMAPClientAbortError:
                # Verify internet connection
                self._network_connected = misc.is_network_connected()

                # If no internet connection established
                if not self._network_connected:
                    
                    # Wait for connection to re-establish
                    self._network_connected = misc.wait_for_network_connection()

                # Else internet connection established
                else:
                    logging.info(f"[{self._bot_name}] Internet connection established!")
                
                # Return to beginning of while-loop
                continue

            # *** Unknown Error ***
            except Exception:
                logging.error(f"[{self._bot_name}] An unknow error occurred!", exc_info=True)

                # Increment login attempts
                login_attempts += 1

        # If the max login attempts allowed has been reached
        if login_attempts == glob.MAX_SMS_LOGIN_ATTEMPTS:
            logging.error(f"[{self._bot_name}] Max number of login attempts have been reached. . . stopping login execution.")

        # If no network connection has been established
        if not self._network_connected:
            logging.error(f"[{self._bot_name}] No network connection found. . . stopping login execution.")
        
        return



    '''
    =========================================================================
    * logout()                                                              *
    =========================================================================
    * This function will logout of the Gmail IMAP and SMTP servers.         *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def logout(self):
        # If network connected
        if self._network_connected:
            logging.info(f"[{self._bot_name}] Logging out of SMS account. . .")

            # Send shutdown message
            self.sms_send_shutdown_message()

            # Remove all SMSBot messages from Gmail
            self.email_sms_cleanup()

            # Logout of IMAP client
            self._imap_client.logout()

            # Reset imap client and login status
            self._imap_client = None
            self._logged_in = False

            logging.info(f"[{self._bot_name}] Successfully logged out!")

        # Else network not connected
        else:
            logging.error(f"[{self._bot_name}] No network connection established!. . . Unable to logout of SMS account!")

        return



    ###################################################
    #   S E N D   M E S S A G E   F U N C T I O N S   #
    ###################################################
    '''
    =========================================================================
    * sms_send_startup_message()                                            *
    =========================================================================
    * This function will send a startup message with a list of exit         *
    * commands to the user/message receiver.                                *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def sms_send_startup_message(self):

        # Send single-part SMS startup message
        logging.info(f"[{self._bot_name}] Sending startup message to {self.format_phone_number()}. . .")
        self.send_singlepart_message(recipient=self._receiver, subject=glob.STARTUP_MSG_SUBJECT, text=glob.SMS_STARTUP)

        return



    '''
    =========================================================================
    * sms_send_message()                                                    *
    =========================================================================
    * This function will send a text message to the message receiver.       *
    *                                                                       *
    *   INPUT:                                                              *
    *         message (str) - The message to be sent to the receiver.       *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def sms_send_message(self, message='', subject=''):
        
        # If subject not provided
        if not subject:

            # Set message subject
            subject = glob.MSG_SUBJECT

        # Send single-part SMS message
        logging.info(f"[{self._bot_name}] Sending message to {self.format_phone_number()}. . .")
        self.send_singlepart_message(recipient=self._receiver, subject=subject, text=message)

        return



    '''
    =========================================================================
    * sms_send_error_message()                                              *
    =========================================================================
    * This function will send an error message to the message receiver      *
    * if they enter an invalid SMSBot command. The current error types      *
    * are listed below:                                                     *
    *                                                                       *
    *       1.) INVALID-CMD: User entered a command that SMSBot does not    *
    *                        understand.                                    *
    *       2.) GENERAL-ERR: General SMSBot error.                          *
    *                                                                       *
    *   INPUT:                                                              *
    *         invalid_cmd (bool) - Invalid SMSBot command error status.     *
    *             general (bool) - General SMSBot error status.             *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def sms_send_error_message(self, invalid_cmd=False, general=False):
        # If invalid command error      
        if invalid_cmd:
            error_text = glob.SMS_ERROR_INVALID_CMD
            error_type = 'Invalid-Cmd'
        
        # Else if general error
        elif general:
            error_text = glob.SMS_ERROR_GENERAL
            error_type = 'General'

        # If any error status is set
        if invalid_cmd or general:
            logging.info(f"[{self._bot_name}] Sending [{error_type}] error message to {self.format_phone_number()}. . .")
            self.send_singlepart_message(recipient=self._receiver, subject=glob.ERROR_MSG_SUBJECT,text=error_text)

        return



    '''
    =========================================================================
    * sms_send_confirmation_message()                                       *
    =========================================================================
    * This function will send a confirmation text message to the message    *
    * receiver to let them know that their message has been received and is *
    * being processed.                                                      *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def sms_send_confirmation_message(self):
        
        # Send single-part SMS confirmation message
        logging.info(f"[{self._bot_name}] Sending confirmation message to {self.format_phone_number()}. . .")
        self.send_singlepart_message(recipient=self._receiver, subject=glob.MSG_SUBJECT, text=glob.SMS_CONFIRM)

        return



    '''
    =========================================================================
    * sms_send_shutdown_message()                                           *
    =========================================================================
    * This function will send a confirmation shutdown message to the        *
    * message receiver.                                                     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def sms_send_shutdown_message(self):

        # Send single-part SMS shutdown confirmation message
        logging.info(f"[{self._bot_name}] Sending shutdown confirmation message to {self.format_phone_number()}. . .")
        self.send_singlepart_message(recipient=self._receiver, subject=glob.SHUTDOWN_MSG_SUBJECT, text=glob.SMS_SHUTDOWN)
        
        return



    ###############################################################
    #   M E S S A G E   P R O C E S S I N G   F U N C T I O N S   #
    ###############################################################
    '''
    =========================================================================
    * wait_for_incoming_messages()                                          *
    =========================================================================
    * This function will listen for incoming text messages from the         *
    * message receiver and process all messages that are received. Each     *
    * message processed is placed in the program queue.                     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def wait_for_incoming_messages(self):

        # If logged in
        if self._logged_in:

            # Access inbox folder
            self._imap_client.select_folder(folder="INBOX")

            logging.info(f"[{self._bot_name}] Listening for messages from {self._receiver}. . .")

            try:
                # Loop while market open and network connection is established
                while (glob.MARKET_OPEN.is_set()) and (self._network_connected):

                    try:
                        # Send NOOP command to reset any auto logout timers
                        self._imap_client.noop()

                        # Wait for new messages from user
                        self._imap_client.idle()
                        incoming_message = self._imap_client.idle_check(timeout=glob.MAX_SMS_IDLE_WAIT_TIME)
                        self._imap_client.idle_done()
                        
                        # If new message received
                        if (incoming_message) and (incoming_message[0][1] == b'EXISTS'):

                            # Search for message(s) from message receiver
                            messages = self._imap_client.search(criteria=[u'FROM', self._receiver, u'SINCE', dt.date.today()])
                            
                            # If message(s) from receiver found
                            if messages:

                                # Get message content from last message received
                                last_message = messages[-1]
                                message_data = self._imap_client.fetch(messages=last_message, data=["RFC822"])

                                # If message data fetched
                                if message_data:
                                    
                                    # Decode message data
                                    message = email.message_from_bytes(message_data[last_message][b'RFC822'])

                                    # Get message information
                                    message_from = message.get("From")
                                    message_text = message.get_payload().replace('\r\n','')
                                    
                                    logging.info(f"[{self._bot_name}] PROCESSING: [UID: {last_message} | FROM: {message_from}]")

                                    # Insert message text into program queue
                                    glob.PROGRAM_QUEUE.put({self._bot_name : message_text})

                                # Else unsuccessfully fetched message contents
                                else:
                                    logging.warning(f"[{self._bot_name}] Unable to fetch message contents for UID {last_message}!")

                                # Delete all messages found from receiver in inbox
                                self._imap_client.delete_messages(messages=messages)

                            # Else message from receiver not found
                            else:
                                logging.warning(f"[{self._bot_name}] No messages found from {self._receiver}!")

                    # *** IMAP Abort Error ***
                    except imap_exceptions.IMAPClientAbortError:
                        # Verify internet connection
                        self._network_connected = misc.is_network_connected()

                        # If no internet connection established
                        if not self._network_connected:
                            
                            # Wait for connection to re-establish
                            self._network_connected = misc.wait_for_network_connection()

                        # If internet connection established
                        if self._network_connected:
                            
                            # IMAP connection no longer usable and should be dropped without logout
                            # Establish new IMAP client, login, and re-access inbox folder
                            self._imap_client = imap.IMAPClient(host=glob.SMS_IMAP_HOST, port=glob.SMS_IMAP_PORT, ssl_context=glob.SMS_SSL)
                            self._imap_client.login(username=self._email, password=self._password)
                            self._imap_client.select_folder(folder="INBOX")

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

            # If network connected
            if self._network_connected:
                self._imap_client.close_folder()    # Close inbox
            
            # Else network not connected
            else:
                logging.error(f"[{self._bot_name}] Unable to close IMAP 'INBOX' folder!")

            logging.info(f"[{self._bot_name}] Successfully exited thread: {self._sms_thread.getName()}")

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")
        
        return



    ###################################################
    #   M E S S A G E   T Y P E   F U N C T I O N S   #
    ###################################################
    '''
    =========================================================================
    * send_singlepart_message()                                             *
    =========================================================================
    * This function will send a single-part message with no attachments to  *
    * the user/message receiver.                                            *
    *                                                                       *
    *   INPUT:                                                              *
    *         recipient (str) - The receiver of the text message.           *
    *           subject (str) - The subject line of the text message.       *
    *              text (str) - The message text.                           *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def send_singlepart_message(self, recipient="", subject="", text=""):

        # Test network connection
        self._network_connected = misc.is_network_connected()
        
        # If network connection established
        if self._network_connected:

            # Create instance of email message
            message = EmailMessage()

            # Set sender, receiver, subject, and message content
            message["From"] = self._email
            message["To"] = recipient
            message["Subject"] = subject
            message.set_content(text)

            # Send message to receiver
            with smtp.SMTP_SSL(host=glob.SMS_SMTP_HOST, port=glob.SMS_SMTP_PORT, context=glob.SMS_SSL) as smtp_client:

                # SMTP login
                smtp_client.login(user=self._email, password=self._password)

                # Send the message
                smtp_client.send_message(msg=message)

                logging.info(f"[{self._bot_name}] Singlepart message sent!")

        # Else no network connection established
        else:
            logging.error(f"[{self._bot_name}] No network connection established!. . . Unable to send singlepart message!")

        return



    '''
    =========================================================================
    * send_multipart_message()                                              *
    =========================================================================
    * This function will send a multipart message with attachments to the   *
    * user/message receiver.                                                *
    *                                                                       *
    *   INPUT:                                                              *
    *         recipient (str) - The receiver of the text message.           *
    *           subject (str) - The subject line of the text message.       *
    *              text (str) - The message text.                           *
    *            kwargs (str) - Keyword arguments used to specify the       *
    *                           type of message attachment. Accepted key-   *
    *                           words are:                                  *
    *                           (+) html: HTML text.                        *
    *                           (+) images: Embedded HTML image(s).         *
    *                           (+) attachments: File attachment(s).        *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def send_multipart_message(self, recipient="", subject="", text="", **kwargs):

        # Test network connection
        self._network_connected = misc.is_network_connected()
        
        # If network connection established
        if self._network_connected:

            # Process html, images, and attachments kwargs
            html = kwargs.get('html')
            images = kwargs.get('images')
            attachments = kwargs.get('attachments')

            # Create overall message object
            message = MIMEMultipart('mixed')
            message['From'] = self._email
            message['To'] = recipient
            message['Subject'] = subject

            # Create the message body and attach the text as "plain text"
            message_body = MIMEMultipart('alternative')
            message_body.attach(MIMEText(text, 'plain'))

            # If HTML included
            if html is not None:

                # Create a new multipart section and attach HTML text
                message_html = MIMEMultipart('related')
                message_html.attach(MIMEText(html, 'html'))

                # If HTML embedded images included
                if images is not None:
    
                    # Open, read, and name the HTML image so that it can be referenced by name in the HTML as:
                    # <img src='cid:image[i]'>, where [i] is the index of the image in images
                    
                    for i in range(len(images or [])):

                        # Open image file
                        fp = open(images[i], 'rb')

                        # Read image and refer image source
                        image_type = images[i].split('.')[-1]
                        image = MIMEImage(fp.read(), _subtype=image_type)
                        image.add_header('Content-ID', "<image{}>".format(i))

                        # Close image file
                        fp.close()

                        # Attach the image to the html part
                        message_html.attach(image)
                
                # Attach the html section to the alternative section
                message_body.attach(message_html)

            # Attach the alternative section to the message
            message.attach(message_body)

            # If attachments included
            if attachments is not None:
                
                # Iterate through all attachment files
                for file in attachments or []:
                    
                    # Open attachment file
                    f = open(file,'rb')

                    # Read in the attachment file and set the header
                    part = MIMEApplication(f.read())
                    part.add_header('Content-Disposition',
                                    'attachment; filename={}'.format(os.path.basename(file)))
                    
                    # Close the file
                    f.close()

                    # Attach the attachment to the message
                    message.attach(part)


            # Send message to receiver
            with smtp.SMTP_SSL(host=glob.SMS_SMTP_HOST, port=glob.SMS_SMTP_PORT, context=glob.SMS_SSL) as smtp_client:

                # SMTP login
                smtp_client.login(user=self._email, password=self._password)

                # Send the message
                smtp_client.send_message(msg=message)

                logging.info(f"[{self._bot_name}] Multipart message sent!")

        # Else no network connection established
        else:
            logging.error(f"[{self._bot_name}] No network connection established!. . . Unable to send multipart message!")

        return



    #####################################################
    #   G M A I L   C L E A N U P   F U N C T I O N S   #
    #####################################################
    '''
    =========================================================================
    * email_sms_cleanup()                                                   *
    =========================================================================
    * This function will remove SMSBot messages from Gmail mailboxes.       *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def email_sms_cleanup(self):
        # Remove SMSBot messages from "Inbox" mailbox
        self._imap_client.select_folder(folder="INBOX")
        messages = self._imap_client.search(criteria=[u'FROM', self._receiver, u'SINCE', dt.date.today()])
        self._imap_client.delete_messages(messages=messages)
        self._imap_client.close_folder()

        # Remove SMSBot messages from "Gmail/Sent Mail" mailbox
        self._imap_client.select_folder(folder="[Gmail]/Sent Mail")
        messages = self._imap_client.search(criteria=[u'TO', self._receiver, u'SINCE', dt.date.today()])
        self._imap_client.delete_messages(messages=messages)
        self._imap_client.close_folder()

        # Remove SMSBot messages from "Gmail/Important" mailbox
        self._imap_client.select_folder(folder="[Gmail]/Important")
        messages = self._imap_client.search(criteria=[u'FROM', self._receiver, u'SINCE', dt.date.today()])
        self._imap_client.delete_messages(messages=messages)
        self._imap_client.close_folder()

        # Remove SMSBot messages from "Gmail/All Mail" mailbox
        # NOTE: "[Gmail]/All Mail" archives messages and will not delete them unless they are moved
        #       to "[Gmail]/Trash" (Example at: http://radtek.ca/blog/delete-old-email-messages-programatically-using-python-imaplib/).

        # Move archived messages from "All Mail" to "Trash"
        self._imap_client.select_folder(folder="[Gmail]/All Mail")
        messages = self._imap_client.search(criteria=[u'TO', self._receiver, u'SINCE', dt.date.today()])
        messages += self._imap_client.search(criteria=[u'FROM', self._receiver, u'SINCE', dt.date.today()])
        self._imap_client.move(messages=messages, folder="[Gmail]/Trash")
        self._imap_client.close_folder()

        # Delete archived messages
        self._imap_client.select_folder(folder="[Gmail]/Trash")
        messages = self._imap_client.search(criteria=[u'TO', self._receiver, u'SINCE', dt.date.today()])
        messages += self._imap_client.search(criteria=[u'FROM', self._receiver, u'SINCE', dt.date.today()])
        self._imap_client.delete_messages(messages=messages)
        self._imap_client.close_folder()

        return



    #########################################
    #   G E N E R A L   F U N C T I O N S   #
    #########################################
    '''
    =========================================================================
    * periodic_noop()                                                       *
    =========================================================================
    * This function will periodically send a NOOP command to prevent timed  *
    * logout of SMSBot due to inactivity.                                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def periodic_noop(self):
        # If logged in
        if self._logged_in:

            # Wait until market open or program shutdown event is set
            while (glob.MARKET_OPEN.is_set()) and (not glob.PROGRAM_SHUTDOWN.is_set()):

                # Calculate time left until market opens
                wait_time = (dt.datetime.combine(dt.date.today(), glob.MARKET_OPEN_TIME) - dt.datetime.now()).total_seconds()

                # If more than <MAX_PERIODIC_NOOP_WAIT_TIME> before market opens
                if wait_time > glob.MAX_PERIODIC_NOOP_WAIT_TIME:

                    # Sleep for <MAX_PERIODIC_NOOP_WAIT_TIME> before sending a NOOP command
                    time.sleep(glob.MAX_PERIODIC_NOOP_WAIT_TIME)

                # Else less than <MAX_PERIODIC_NOOP_WAIT_TIME> before market opens
                else:

                    # Sleep for <wait_time> before sending a NOOP command
                    time.sleep(wait_time)

                # Send NOOP command
                self._imap_client.noop()

        # Else not logged in
        else:
            logging.warning(f"[{self._bot_name}] Not logged in!")

        return



    '''
    =========================================================================
    * is_logged_in()                                                        *
    =========================================================================
    * This function will return the SMSBot login status.                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         logged_in (bool) - Logged in status flag for SMSBot.          *
    =========================================================================
    '''
    def is_logged_in(self):
        return self._logged_in



    '''
    =========================================================================
    * get_name()                                                            *
    =========================================================================
    * This function will return the SMSBot name.                            *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         bot_name (str) - The SMSBot name.                             *
    =========================================================================
    '''
    def get_name(self):
        return self._bot_name



    '''
    =========================================================================
    * format_phone_number()                                                 *
    =========================================================================
    * This function will format phone number as ###-####.                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         format_number (str) - The user phone number formatted as      *
    *                               (###-####).                             *
    =========================================================================
    '''
    def format_phone_number(self):
        # Initialize formatted phone number
        formatted_phone_number = ""

        # If phone number provided
        if self._phone_number:

            # Format phone number
            formatted_phone_number = format(int(self._phone_number[:-1]), ",").replace(",","-") + self._phone_number[-1]

        # Else phone number not provided
        else:
            logging.error(f"[{self._bot_name}] Phone number required in order to format!")

        return formatted_phone_number
