'''
=========================================================================
* cr_globals.py                                                         *
=========================================================================
* This file contains all global variables used by Cryptor.              *
=========================================================================
'''
import datetime as dt


###################################################################
#   G L O B A L   P A T H S   A N D   V A R I A B L E S           #
###################################################################
LOGGER_PATH             :   str     = f"/logs/cryptor/"                         # Path to Cryptor log files
LOGGER_FILE_NAME        :   str     = f"cryptor_{dt.datetime.today().date()}"   # Cryptor log file name
LOGGER_EXT              :   str     = ".log"                                    # Log file extension

#####################################################################
#   E N C R Y P T I O N / D E C R Y P T I O N   V A R I A B L E S   #
#####################################################################
CRYPTOR_KEY_FILE_NAME   :   str     = "cryptor_key.key"                         # Encryption/Decryption key file name
ENCRYPT_EXT             :   str     = ".aes"                                    # Encrypted File Extension
DECRYPT_EXT             :   str     = ".config"                                 # Decrypted File Extension