'''
=============================================================================
* cr_gui.py                                                                 *
=============================================================================
* This file contains the Cryptor GUI class and all functions associated     *
* with the creation of a Cryptor program graphical user interface.          *
=============================================================================
'''
import os
import tkinter as tk
import source.cryptor.cr_misc as cr_m
import source.cryptor.cr_globals as cr_g

from tkinter.ttk import Combobox
from source.cryptor.cr_cryptor import Cryptor
from tkinter.filedialog import askopenfilename
from tkinter.messagebox import showinfo, showwarning


class CryptorGUI:
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes the Cryptor GUI window.                     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self) -> None:

        # Create Cryptor main GUI window
        self._cr_win = tk.Tk()
        self._cr_win.title("CRYPTOR")
        self._cr_win.geometry("450x230+80+80")  # width x height + xPos + yPos
        self._cr_win.resizable(False, False)

        # Set input and output file types
        self._encrypted_file_type = [('aes files', '*.aes')]
        self._decrypted_file_type = [('config files', '*.config')]

        # Set background color
        self._background = "#71797E"
        self._cr_win["background"] = self._background

        # Draw labels and buttons to window
        self._create()

        return



    '''
    =========================================================================
    * _create()                                                             *
    =========================================================================
    * This function draws all all appropriate labels and buttons used to    *
    * create a graphical user interface for the Cryptor program.            *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _create(self) -> None:
        # Create Cryptor 'Mode' label and combo box
        self._mode_label = tk.Label(self._cr_win, text="Mode")
        self._mode_cb = Combobox(self._cr_win, values=["Encrypt", "Decrypt"], state="readonly")

        # Place location for 'Mode' label and combo box
        self._mode_label.place(x=70, y=40)
        self._mode_label["background"] = self._background
        self._mode_cb.place(x=120, y=40)
        self._mode_cb.current(0)


        # Create Cryptor 'Input File' label, entry, and button
        self._input_label = tk.Label(self._cr_win, text="Input File")
        self._input_label["background"] = self._background
        self._input_entry = tk.Entry(width=23, textvariable="")
        self._input_search = tk.Button(self._cr_win, text="Browse", command=self._get_input_file)

        # Place location for 'Input File' label, entry, and button
        self._input_label.place(x=50, y=70)
        self._input_entry.place(x=120, y=70)
        self._input_search.place(x=345, y=70)
        

        # Create Cryptor 'Output File' label, entry, and buton
        self._output_label = tk.Label(self._cr_win, text="Output File")
        self._output_label["background"] = self._background
        self._output_entry = tk.Entry(width=23, textvariable="")
        self._output_search = tk.Button(self._cr_win, text="Browse", command=self._get_output_file)

        # Place location for 'Output File' label, entry, and button
        self._output_label.place(x=40, y=105)
        self._output_entry.place(x=120, y=105)
        self._output_search.place(x=345, y=105)


        # Create Cryptor 'Keep Original' checkbox option
        self._keep_orig_val = tk.BooleanVar()
        self._keep_orig_check = tk.Checkbutton(self._cr_win, text="Keep Original Input File", variable=self._keep_orig_val,
                                               onvalue=True, offvalue=False, activebackground=self._background)
        self._keep_orig_check["background"] = self._background

        # Place location for 'Keep Original' checkbox
        self._keep_orig_check.place(x=145, y=140)


        # Create Cryptor 'Execute' button
        self._execute = tk.Button(self._cr_win, text="Execute", width=25, command=self._cryptor_exec)

        # Place location for 'Execute' button
        self._execute.place(x=100, y=175)

        return



    '''
    =========================================================================
    * _cryptor_exec()                                                       *
    =========================================================================
    * This function executes cryptor encryption/decryption task.            *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _cryptor_exec(self) -> None:
        cr_m.setup_logger()                                # Setup cryptor logger

        # +++++++++++++++++++++++++++++++++++++
        #           Verify input
        # +++++++++++++++++++++++++++++++++++++
        # [ MODE ]
        if self._mode_cb.get().upper() == "ENCRYPT":    # Encryption mode
            encrypt, decrypt = True, False
        else:                                           # Decryption mode
            encrypt, decrypt = False, True


        # [ INPUT FILE ]
        input_file = self._input_entry.get()

        # If input file not provided
        if not input_file:
            # Show warning dialog
            warning_message = "Need to provide an input file!"
            showwarning(title="Invalid Input File", message=warning_message)

            return

        # Else if input file does not end in *.config or *.aes
        elif (not input_file.endswith(cr_g.DECRYPT_EXT)) and (not input_file.endswith(cr_g.ENCRYPT_EXT)):
            # Show warning dialog
            warning_message = "Input file needs to be a '.config' or '.aes' file!"
            showwarning(title="Invalid Input File", message=warning_message)

            return


        # [ OUTPUT FILE ]
        output_file = self._output_entry.get()

        # If output file does not end in *.config or *.aes
        if (output_file) and ((not output_file.endswith(cr_g.DECRYPT_EXT)) and (not output_file.endswith(cr_g.ENCRYPT_EXT))):
            # Show warning dialog
            warning_message = "Output file needs to be a '.config' or '.aes' file!"
            showwarning(title="Invalid Output File", message=warning_message)

            return


        # Display warning banner
        self._display_warning_banner()

        # Execute encryption or decryption
        cryptor = Cryptor(encrypt=encrypt, decrypt=decrypt, input=input_file, output=output_file, 
                          keep_original=self._keep_orig_val.get())
        cryptor._execute()

        # Display completion window
        complete_message = f"Cryptor Execution Complete!\n\nPlease view the log files if there are any issues:\n{os.getcwd()}/logs/cryptor"
        showinfo(title="Execution Complete", message=complete_message)
        
        cr_m.shutdown_logger()                             # Shutdown cryptor logger

        return



    '''
    =========================================================================
    * _display_warning_banner()                                             *
    =========================================================================
    * This function displays the Cryptor program warning banner.            *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _display_warning_banner(self) -> None:
        # Create warning message
        warning_message = ""
        warning_message += "ALWAYS CHECK THE CONTENTS OF THE OUTPUT FILE AFTER ENCRYPTION TO ENSURE THAT THE DATA IS PROPERLY "
        warning_message += "PROTECTED. SIMILARLY, ALWAYS CHECK THE CONTENTS OF THE OUTPUT FILE AFTER DECRYPTION TO ENSURE THAT "
        warning_message += "DATA HAS BEEN PROPERLY DECRYPTED.\n\n"
        warning_message += "NEVER ASSUME THAT YOUR DATA HAS BEEN ENCRYPTED OR DECRYPTED BASED OFF THE MESSAGES THAT THIS PROGRAM " 
        warning_message += "PRODUCES."

        # Show warning dialog
        showwarning(title="!!! PLEASE READ !!!",
                    message=warning_message)

        return



    '''
    =========================================================================
    * _get_input_file()                                                     *
    =========================================================================
    * This function opens a file dialog and prompts the user for an input   *
    * config file to encrypt or decrypt.                                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _get_input_file(self) -> None:
        # Determine filetype to search for
        if self._mode_cb.get().upper() == "ENCRYPT":    # Encrypt mode
            filetype = self._decrypted_file_type
        else:                                           # Decrypt mode
            filetype = self._encrypted_file_type

        # Open file dialog
        filename = askopenfilename(title="Select input file",
                                    initialdir=os.getcwd(), 
                                    filetypes=filetype)

        # Write input file path in entry
        if self._input_entry.index("end") != 0:
            self._input_entry.delete(0, tk.END)
        self._input_entry.insert(tk.END, filename)

        return



    '''
    =========================================================================
    * _get_output_file()                                                    *
    =========================================================================
    * This function opens a file dialog and prompts the user for an output  *
    * file to write to.                                                     *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _get_output_file(self):
        # Determine filetype to search for
        if self._mode_cb.get().upper() == "ENCRYPT":    # Encrypt mode
            filetype = self._encrypted_file_type
        else:                                           # Decrypt mode
            filetype = self._decrypted_file_type

        # Open file dialog
        filename = askopenfilename(title="Select output file",
                                    initialdir=os.getcwd(), 
                                    filetypes=filetype)

        # Create file if it does not exists
        if filename and not os.path.exists(filename):
            open(filename, "w+").close()

        # Write output file path in entry
        if self._output_entry.index("end") != 0:
            self._output_entry.delete(0, tk.END)
        self._output_entry.insert(tk.END, filename)

        return



    '''
    =========================================================================
    * _show_window()                                                        *
    =========================================================================
    * This function shows the Cryptor program GUI.                          *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _show_window(self) -> None:
        self._cr_win.mainloop()     # Show the cryptor window

        return
