'''
=============================================================================
* mt_gui.py                                                                 *
=============================================================================
* This file contains the Mirror Trader GUI class and all functions that     *
* will be associated with the creation of a Mirror Trader program graphical *
* user interface.                                                           *
=============================================================================
'''
import os
import tkinter as tk
import source.mirror_trader.mt_globals as mt_g

from tkinter.messagebox import showwarning
from tkinter.filedialog import askopenfilename


class MirrorTraderGUI:
    '''
    =========================================================================
    * __init__()                                                            *
    =========================================================================
    * This function initializes the Mirror Trader GUI window.               *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def __init__(self) -> None:

        self._mt_win            :   tk.Tk           = tk.Tk()                   # Initialize MirrorTrader main GUI window
        self._config            :   str             = ""                        # Initialize config file path
        self._debug             :   bool            = False                     # Initialize debug status flag
        self._developer         :   bool            = False                     # Initialize developer status flag
        self._valid_input       :   bool            = False                     # Initialize valid input status flag
        self._config_file_types :   list[set(str)]  = [('config file types',    # Initialize file type inputs
                                                        '*.aes *.config')]
        self._background        :   str             = "#71797E"                 # Initialize background color       

        # Create Mirror Trader main GUI window
        self._mt_win["background"]                  = self._background          # Set main window background color
        self._mt_win.title("MIRROR TRADER")                                     # Set main window title
        self._mt_win.geometry("450x200+80+80")                                  # Set main window size and position (width x height + xPos + yPos)
        self._mt_win.resizable(width=False, height=False)                       # Set main window resizable status
        
        # Draw labels and buttons to window
        self._create()

        return



    '''
    =========================================================================
    * _create()                                                             *
    =========================================================================
    * This function draws all all appropriate labels and buttons used to    *
    * create a graphical user interface for the Mirror Trader program.      *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _create(self) -> None:
    
        # Create Mirror Trader 'Input File' label, entry, and button
        self._input_label = tk.Label(self._mt_win, text="Config File")
        self._input_label["background"] = self._background
        self._input_entry = tk.Entry(width=23, textvariable="")
        self._input_search = tk.Button(self._mt_win, text="Browse", command=self._get_input_file)

        # Place location for 'Input File' label, entry, and button
        self._input_label.place(x=25, y=50)
        self._input_entry.place(x=100, y=50)
        self._input_search.place(x=325, y=50)


        # Create Mirror Trader 'Debug Mode' checkbox option
        self._debug_mode = tk.BooleanVar()
        self._debug_mode_check = tk.Checkbutton(self._mt_win, text="Debug Mode", variable=self._debug_mode,
                                                onvalue=True, offvalue=False, activebackground=self._background)
        self._debug_mode_check["background"] = self._background

        # Place location for 'Debug Mode' checkbox
        self._debug_mode_check.place(x=115, y=90)


        # Create Mirror Trader 'Developer Mode' checkbox option
        self._developer_mode = tk.BooleanVar()
        self._developer_mode_check = tk.Checkbutton(self._mt_win, text="Developer Mode", variable=self._developer_mode,
                                                    onvalue=True, offvalue=False, activebackground=self._background)
        self._developer_mode_check["background"] = self._background

        # Place location for 'Developer Mode' checkbox
        self._developer_mode_check.place(x=250, y=90)


        # Create Mirror Trader 'Execute' button
        self._execute = tk.Button(self._mt_win, text="Execute Mirror Trader", width=25, command=self._verify_input)

        # Place location for 'Execute' button
        self._execute.place(x=100, y=130)

        return



    '''
    =========================================================================
    * _verify_input()                                                       *
    =========================================================================
    * This function verifies the input for Mirror Trader execution.         *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _verify_input(self) -> None:
    
        # [ INPUT FILE ]
        input_file = self._input_entry.get()

        # If input file not provided
        if not input_file:
            # Show warning dialog
            warning_message = "Need to provide an input config file!"
            showwarning(title="Invalid Input File", message=warning_message)
            return

        # Else if input file does not end in *.config or *.aes
        elif (not input_file.endswith(mt_g.DECRYPT_EXT)) and (not input_file.endswith(mt_g.ENCRYPT_EXT)):
            # Show warning dialog
            warning_message = "Input file needs to be a '.config' or '.aes' file!"
            showwarning(title="Invalid Input File", message=warning_message)
            return


        # [ DEVELOPER MODE ]
        # If developer mode selected and input file does not end in *.config
        if (self._developer_mode.get()) and (not input_file.endswith(mt_g.DECRYPT_EXT)):
            # Show warning dialog
            warning_message = "Input file needs to be a '.config' file if 'Developer Mode' is enabled!"
            showwarning(title="Invalid Input File", message=warning_message)
            return
        
        # Else if developer mode not selected and input file does not end in *.aes
        elif (not self._developer_mode.get()) and (not input_file.endswith(mt_g.ENCRYPT_EXT)):
            # Show warning dialog
            warning_message = "Input file needs to be a '.aes' file if 'Developer Mode' is not enabled!"
            showwarning(title="Invalid Input File", message=warning_message)
            return
        
        self._mt_win.destroy()
        self._mt_win.quit()
        self._mt_win.update()

        self._valid_input   = True
        self._config        = input_file
        self._debug         = self._debug_mode.get()
        self._developer     = self._developer_mode.get()

        return



    '''
    =========================================================================
    * _get_input_file()                                                     *
    =========================================================================
    * This function opens a file dialog and prompts the user for an input   *
    * config file to use.                                                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _get_input_file(self):

        # Open file dialog
        filename = askopenfilename(title="Select input file",
                                    initialdir=os.getcwd(), 
                                    filetypes=self._config_file_types)

        # Write input file path in entry
        if self._input_entry.index("end") != 0:
            self._input_entry.delete(0, tk.END)
        self._input_entry.insert(tk.END, filename)

        return



    '''
    =========================================================================
    * _input_valid()                                                        *
    =========================================================================
    * This function opens a file dialog and prompts the user for an input   *
    * config file to use.                                                   *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _input_valid(self):
        return self._valid_input



    '''
    =========================================================================
    * _show_window()                                                        *
    =========================================================================
    * This function shows the Mirror Trader program GUI.                    *
    *                                                                       *
    *   INPUT:                                                              *
    *         None                                                          *
    *                                                                       *
    *   OUPUT:                                                              *
    *         None                                                          *
    =========================================================================
    '''
    def _show_window(self):
        self._mt_win.mainloop()     # Show the mirror trader window

        return
