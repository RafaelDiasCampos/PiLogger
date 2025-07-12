from src.VirtualKeyboard import VirtualKeyboard

def main():
    log_name = "keyboard_log"
    
    virtualKeyboard = VirtualKeyboard(log_name=log_name)
    virtualKeyboard.process_log_file(f"{log_name}.raw")    
    
            
if __name__ == "__main__":
    main()