'''
=========================================================================
* mirror_trader.py                                                      *
=========================================================================
* Background:                                                           *
* --------------------------------------------------------------------- *
* This is the console version of the Mirror Trader program written      *
* entirely in python. Mirror Trader is a program that follows and       *
* places option trade alerts sent out by executive members of various   *
* stock trading Discord groups.                                         *
*                                                                       *
* The program will listen for new buy or sell alerts from an options    *
* alert channel. When a new alert has been collected, the program will  *
* utilize Webull Financial's API to place the buy or sell order.        *
* Mirror Trader will manage risk by placing stop loss orders for all    *
* buy orders placed and will update stop loss prices as options are     *
* sold.                                                                 *
*                                                                       *
* The program supports paper-trading and live-trading and features the  *
* ability to shutdown execution using SMS commands.                     *
=========================================================================
'''
import source.mirror_trader.mt_gui as gui
import source.mirror_trader.mt_main as main


if __name__ == "__main__":
    trader = gui.MirrorTraderGUI()  # Create MirrorTrader GUI
    trader._show_window()           # Display main window

    # If mirror trader input has been validated
    if trader._input_valid():
        # Execute mirror trader program
        main.execute(config=trader._config, debug=trader._debug, dev=trader._developer)


