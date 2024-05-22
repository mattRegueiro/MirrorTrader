'''
=============================================================================
* cr_cryptor.py                                                             *
=============================================================================
* This file contains the Cryptor class and all functions associated with    *
* encrypting and decrypting a user's configuration file.                    *
=============================================================================
'''
import os
import logging

from cryptography.fernet import Fernet
from source.cryptor import cr_globals as cr_g


class Cryptor():
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes all all appropriate flags, lists, and       *
    * tables used to handle the processing of encrypting and decrypting a   *
    * user's config file.                                                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         encrypt (bool) - Encryption mode enabled flag.                *
    *         decrypt (bool) - Decryption mode enabled flag.                *
    *            input (str) - Input file to encrypt/decrypt.               *
    *           output (str) - Output file to write to.                     *
    *   keep_original (bool) - Flag to keep original data before            *
    *                          encryption/decryption.                       *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self, encrypt: bool=False, decrypt: bool=False, input: str="", 
                 output: str="", keep_original: bool=False) -> None:

        # Set encrypt/decrypt mode execution flags
        self._encrypt           : bool      = encrypt
        self._decrypt           : bool      = decrypt

        # Set input and output file names
        self._input             : str       = input
        self._output            : str       = output

        # Set "Keep Original" status flag and bot name
        self._keep_original     : bool      = keep_original
        self._bot_name          : str       = str(self.__class__.__name__)

        # Initialize encryption/decryption key
        self._key               : Fernet    = None

        return



    '''
    =========================================================================
    * _execute()                                                            *
    =========================================================================
    * This function executes the Cryptor encryption/decryption task.        *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _execute(self) -> bool:

        # Initialize execution complete status
        execution_done  : bool  = False

        logging.info("++ Beginning CRYPTOR program execution. . .")

        # If input file not provided
        if not self._input:
            logging.error(f"++ Need to provide a config file input in order to encrypt or decrypt config file data!")
            return execution_done
        
        # If input file does not end with .aes or .config
        if not(self._input.endswith(cr_g.ENCRYPT_EXT) or self._input.endswith(cr_g.DECRYPT_EXT)):
            logging.error(f"++ Need to provide a '.aes' or '.config' input file!")
            return execution_done

        # Get encryption/decryption key
        self._key = self._get_key()

        # If input file found in working dir
        if os.path.exists(self._input):

            # Generate fernet instance using personal key
            fernet = Fernet(key=self._key)
            
            # Read data from input file
            with open(self._input, 'rb') as f:
                data = f.read()

            # If both encryption and decryption commanded
            if (self._encrypt) and (self._decrypt):
                logging.error(f"++ Cannot execute encryption and decryption simultaneously!")
                return execution_done

            # Else encryption or decryption commanded
            else:

                # If config encryption commanded
                if self._encrypt:
                    execution_done = self._execute_encryption(fernet=fernet, data=data)

                # Else if config decryption commanded
                elif self._decrypt:
                    execution_done = self._execute_decryption(fernet=fernet, data=data)

        # Else input file is not found
        else:
            logging.error(f"++ Could not find input file: {self._input}")

        return execution_done



    '''
    =========================================================================
    * _execute_encryption()                                                 *
    =========================================================================
    * This function executes the Cryptor encryption task.                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         fernet (Fernet) - Fernet instance for encryption/decryption.  *
    *           data (string) - Data from decrypted config file.            *
    *                                                                       *
    *   OUPUT:                                                              *
    *     encrypt_done (bool) - Encryption complete status flag.            *
    =========================================================================
    '''
    def _execute_encryption(self, fernet: Fernet=None, data: str=None) -> bool:
        # Initialize encryption execution status
        encrypt_done    : bool  = False

        # If fernet instance or data not provided
        if (not fernet) or (not data):
            logging.error(f"++ Missing fernet instance or data!")
            return encrypt_done

        logging.info(f"++ Running encryption mode on {self._input}. . .")

        # If input file already encrypted
        if cr_g.ENCRYPT_EXT in self._input:
            logging.info(f"++ Input file: {self._input} is already encrypted!")
            return encrypt_done

        # Else encrypt data from credentials config file
        encrypted_data = fernet.encrypt(data=data)

        # If output file provided
        if self._output:

            # If decrypt file extension included in output file name
            if cr_g.DECRYPT_EXT in self._output:

                # Replace decrypt file extension with encrypt file extension
                self._output = self._output.replace(cr_g.DECRYPT_EXT, cr_g.ENCRYPT_EXT)

            # Else if encrypt file extension not included in output file name
            elif cr_g.ENCRYPT_EXT not in self._output:

                # Add encrypt file extension to output file name
                self._output += cr_g.ENCRYPT_EXT

        # Else output file not provided
        else:
            self._output = self._input.replace(cr_g.DECRYPT_EXT, cr_g.ENCRYPT_EXT)

        # Write encrypted data to output file
        with open(self._output, 'wb') as f:
            f.write(encrypted_data)

        # If "Keep Original" status flag not set
        if not self._keep_original:
            os.remove(self._input)
        
        logging.info(f"++ Done with encryption execution!")
        encrypt_done = True
        
        return encrypt_done



    '''
    =========================================================================
    * _execute_decryption()                                                 *
    =========================================================================
    * This function executes the Cryptor decryption task.                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         fernet (Fernet) - Fernet instance for encryption/decryption.  *
    *           data (string) - Data from encrypted config file.            *
    *                                                                       *
    *   OUPUT:                                                              *
    *     decrypt_done (bool) - Decryption complete status flag.            *
    =========================================================================
    '''
    def _execute_decryption(self, fernet: Fernet=None, data: str=None) -> bool:
        # Initialize decryption execution status
        decrypt_done    : bool  = False

        # If fernet instance or data not provided
        if (not fernet) or (not data):
            logging.error(f"++ Missing fernet instance or data!")
            return decrypt_done

        logging.info(f"++ Running decryption mode on {self._input}. . .")

        # If input file already decrypted
        if cr_g.DECRYPT_EXT in self._input:
            logging.info(f"++ Input file: {self._input} is already decrypted!")
            return decrypt_done

        # Else decrypt data from encrypted credentials config file
        decrypted_data = fernet.decrypt(token=data)

        # If output file provided
        if self._output:

            # If encrypt file extension included in output file name
            if cr_g.ENCRYPT_EXT in self._output:

                # Replace encrypt file extension with decrypt file extension
                self._output = self._output.replace(cr_g.ENCRYPT_EXT, cr_g.DECRYPT_EXT)

            # Else if decrypt file extension not included in output file name
            elif cr_g.DECRYPT_EXT not in self._output:

                # Add decrypt file extension to output file name
                self._output += cr_g.DECRYPT_EXT

        # Else output file not provided
        else:
            self._output = self._input.replace(cr_g.ENCRYPT_EXT, cr_g.DECRYPT_EXT)

        # Write decrypted data to output file
        with open(self._output, 'wb') as f:
            f.write(decrypted_data)

        # If "Keep Original" status flag not set
        if not self._keep_original:
            os.remove(self._input)

        logging.info(f"++ Done with decryption execution!")
        decrypt_done = True

        return decrypt_done



    '''
    =========================================================================
    * _get_key()                                                            *
    =========================================================================
    * This function finds or generates an encryption/decryption key.        *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         key (Fernet) - The encryption/decryption key.                 *
    =========================================================================
    '''
    def _get_key(self) -> Fernet:

        # Initialize encryption/decryption key
        key : Fernet    = None

        # If encryption/decryption key file found
        if os.path.exists(cr_g.CRYPTOR_KEY_FILE_NAME):

            logging.info(f"++ Encrypt/Decrypt key found!")

            # Open encryption/decryption key file and get key value
            with open(cr_g.CRYPTOR_KEY_FILE_NAME, 'rb') as file:
                key = file.read()

        # Else encryption/decryption key file not found
        else:

            logging.warning(f"++ Could not find encrypt/decrypt key!. . . Generating new key. . .")

            # Generate new encryption/decryption key
            key = Fernet.generate_key()

            # Save key to file
            with open(cr_g.CRYPTOR_KEY_FILE_NAME, 'wb') as file:
                file.write(key)

            logging.info(f"++ Key generated!")

        return key
