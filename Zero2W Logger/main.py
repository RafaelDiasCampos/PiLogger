from src.VirtualKeyboard import VirtualKeyboard
from src.KeyboardSniffer import KeyboardSniffer

def main():
    log_name = "keyboard_log"
    
    decoder = KeyboardSniffer()
    virtualKeyboard = VirtualKeyboard(log_name=log_name)
    
    print("Listening for keyboard input... Press Ctrl+C to exit.")
    
    try:
        for mod, keycodes in decoder.get_keycodes():
            virtualKeyboard.process_hid_report(mod, keycodes)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        decoder.ser.close()
            
if __name__ == "__main__":
    main()