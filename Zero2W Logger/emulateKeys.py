from src.VirtualKeyboard import VirtualKeyboard
import time

def main():
    log_name = "keyboard_log"
    
    virtualKeyboard = VirtualKeyboard(log_name=log_name)
    
    time.sleep(1)
    
    virtualKeyboard.process_log_file(f"{log_name}.raw")    
    
            
if __name__ == "__main__":
    main()