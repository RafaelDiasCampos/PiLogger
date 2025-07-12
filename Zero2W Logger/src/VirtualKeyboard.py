import uinput
import time
from evdev import ecodes


class VirtualKeyboard:
    def __init__(self, create_keyboard: bool = True, log_name: str | None = None) -> None:
        self.create_keyboard = create_keyboard
        self.log_name = log_name

        self.hid_to_linux_key, self.hid_modifiers = self.get_hid_tables()
        self.key_to_ascii = self.get_key_to_ascii_table()
        self.pressed_keys = set()  # To track currently pressed keys

        # If create_keyboard is True, initialize the uinput device
        if self.create_keyboard:
            self.uinput_device = uinput.Device(
                list(set(self.hid_to_linux_key.values()) | set(self.hid_modifiers.values())))

        # If a log name is specified, open the files for writing
        if self.log_name:
            try:
                # Append mode 'a' is used to keep the log file persistent
                self.log_raw = open(f"{self.log_name}.raw", "a")
                self.log_text = open(f"{self.log_name}.txt", "a")
            except IOError as e:
                raise IOError(f"Could not open log name {self.log_name}: {e}")

        # Last timestamp for logging
        self.last_log_time = 0

        self.modifiers_state = {
            uinput.KEY_LEFTCTRL: False,
            uinput.KEY_LEFTSHIFT: False,
            uinput.KEY_LEFTALT: False,
            uinput.KEY_LEFTMETA: False,
            uinput.KEY_RIGHTCTRL: False,
            uinput.KEY_RIGHTSHIFT: False,
            uinput.KEY_RIGHTALT: False,
            uinput.KEY_RIGHTMETA: False
        }

    def __del__(self):
        # Close the log file handle if it was opened
        if self.log_name:
            if hasattr(self, 'log_raw'):
                self.log_raw.close()
            if hasattr(self, 'log_text'):
                self.log_text.close()

    def log_event(self, key: int | tuple[int, int], action: str) -> None:
        if not self.log_raw:
            return

        current_time = time.time()

        # If the last log time is more than 5 minutes ago, write a timestamp
        if current_time - self.last_log_time > 300:  # 5 minutes
            log_text = f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}\n"
            self.log_raw.write(log_text)
            self.log_text.write(log_text)

        # Log the raw key event
        key_code = key[1] if isinstance(key, tuple) else key
        key_name = ecodes.KEY[key_code] if key_code in ecodes.KEY else str(
            key_code)
        self.log_raw.write(f"{action}: {key_name}\n")
        self.log_raw.flush()

        # Log the text representation
        if action == "pressed" and key in self.key_to_ascii:
            ascii_char = self.key_to_ascii[key]
            if self.modifiers_state[uinput.KEY_LEFTSHIFT] or self.modifiers_state[uinput.KEY_RIGHTSHIFT]:
                ascii_char = ascii_char[1]
            else:
                ascii_char = ascii_char[0]
            self.log_text.write(ascii_char)
            self.log_text.flush()

        self.last_log_time = current_time

    def process_hid_report(self, mod: int, keycodes: list[int]) -> None:
        new_pressed_keys = set()

        # Convert HID keycodes to Linux keycodes
        for keycode in keycodes:
            if keycode in self.hid_to_linux_key:
                linux_key = self.hid_to_linux_key[keycode]
                new_pressed_keys.add(linux_key)
            else:
                raise ValueError(f"Unknown keycode: {keycode}")

        # Handle modifiers
        for modifier in self.hid_modifiers:
            if mod & modifier:
                new_pressed_keys.add(self.hid_modifiers[modifier])

        # Determine keys that were pressed or released
        keys_to_press = new_pressed_keys - self.pressed_keys
        keys_to_release = self.pressed_keys - new_pressed_keys

        # Press new keys
        for key in keys_to_press:
            # Update modifier state
            if key in self.modifiers_state:
                self.modifiers_state[key] = True

            # Emit the key press event
            if self.create_keyboard:
                self.uinput_device.emit(key, 1)

            # Log the key press event
            self.log_event(key, "pressed")

        # Release old keys
        for key in keys_to_release:
            # Update modifier state
            if key in self.modifiers_state:
                self.modifiers_state[key] = False

            # Emit the key press event
            if self.create_keyboard:
                self.uinput_device.emit(key, 0)

            # Log the key press event
            self.log_event(key, "released")

        # Update the currently pressed keys
        self.pressed_keys = new_pressed_keys
        
    def process_log_file(self, log_file: str) -> None:
        if not self.create_keyboard:
            raise RuntimeError("VirtualKeyboard not initialized with create_keyboard=True")
        
        try:
            with open(log_file, 'r') as file:
                for line in file:
                    parts = line.strip().split(': ')
                    if len(parts) == 2:
                        action, key_name = parts
                        key_name = key_name.strip()
                        
                        # Reverse lookup on ecodes.KEY to get the key code
                        key = next((k for k, v in ecodes.KEY.items() if v == key_name), None)
                        
                        key = (1, key) if key is not None else None
                        
                        if key is not None:
                            if action == "pressed":
                                self.uinput_device.emit(key, 1)
                            elif action == "released":
                                self.uinput_device.emit(key, 0)
                        
        except IOError as e:
            print(f"Error reading log file {log_file}: {e}")

    def get_hid_tables(self) -> tuple[dict[int, tuple[int, int]], dict[int, int]]:
        hid_to_linux_key = {
            0x04: uinput.KEY_A,
            0x05: uinput.KEY_B,
            0x06: uinput.KEY_C,
            0x07: uinput.KEY_D,
            0x08: uinput.KEY_E,
            0x09: uinput.KEY_F,
            0x0A: uinput.KEY_G,
            0x0B: uinput.KEY_H,
            0x0C: uinput.KEY_I,
            0x0D: uinput.KEY_J,
            0x0E: uinput.KEY_K,
            0x0F: uinput.KEY_L,
            0x10: uinput.KEY_M,
            0x11: uinput.KEY_N,
            0x12: uinput.KEY_O,
            0x13: uinput.KEY_P,
            0x14: uinput.KEY_Q,
            0x15: uinput.KEY_R,
            0x16: uinput.KEY_S,
            0x17: uinput.KEY_T,
            0x18: uinput.KEY_U,
            0x19: uinput.KEY_V,
            0x1A: uinput.KEY_W,
            0x1B: uinput.KEY_X,
            0x1C: uinput.KEY_Y,
            0x1D: uinput.KEY_Z,
            0x1E: uinput.KEY_1,
            0x1F: uinput.KEY_2,
            0x20: uinput.KEY_3,
            0x21: uinput.KEY_4,
            0x22: uinput.KEY_5,
            0x23: uinput.KEY_6,
            0x24: uinput.KEY_7,
            0x25: uinput.KEY_8,
            0x26: uinput.KEY_9,
            0x27: uinput.KEY_0,
            0x28: uinput.KEY_ENTER,
            0x29: uinput.KEY_ESC,
            0x2A: uinput.KEY_BACKSPACE,
            0x2B: uinput.KEY_TAB,
            0x2C: uinput.KEY_SPACE,
            0x2D: uinput.KEY_MINUS,
            0x2E: uinput.KEY_EQUAL,
            0x2F: uinput.KEY_LEFTBRACE,
            0x30: uinput.KEY_RIGHTBRACE,
            0x31: uinput.KEY_BACKSLASH,
            0x32: uinput.KEY_102ND,
            0x33: uinput.KEY_SEMICOLON,
            0x34: uinput.KEY_APOSTROPHE,
            0x35: uinput.KEY_GRAVE,
            0x36: uinput.KEY_COMMA,
            0x37: uinput.KEY_DOT,
            0x38: uinput.KEY_SLASH,
            0x39: uinput.KEY_CAPSLOCK,
            0x3A: uinput.KEY_F1,
            0x3B: uinput.KEY_F2,
            0x3C: uinput.KEY_F3,
            0x3D: uinput.KEY_F4,
            0x3E: uinput.KEY_F5,
            0x3F: uinput.KEY_F6,
            0x40: uinput.KEY_F7,
            0x41: uinput.KEY_F8,
            0x42: uinput.KEY_F9,
            0x43: uinput.KEY_F10,
            0x44: uinput.KEY_F11,
            0x45: uinput.KEY_F12,
            0x46: uinput.KEY_SYSRQ,
            0x47: uinput.KEY_SCROLLLOCK,
            0x48: uinput.KEY_PAUSE,
            0x49: uinput.KEY_INSERT,
            0x4A: uinput.KEY_HOME,
            0x4B: uinput.KEY_PAGEUP,
            0x4C: uinput.KEY_DELETE,
            0x4D: uinput.KEY_END,
            0x4E: uinput.KEY_PAGEDOWN,
            0x4F: uinput.KEY_RIGHT,
            0x50: uinput.KEY_LEFT,
            0x51: uinput.KEY_DOWN,
            0x52: uinput.KEY_UP,
            0x53: uinput.KEY_NUMLOCK,
            0x54: uinput.KEY_KPSLASH,
            0x55: uinput.KEY_KPASTERISK,
            0x56: uinput.KEY_KPMINUS,
            0x57: uinput.KEY_KPPLUS,
            0x58: uinput.KEY_KPENTER,
            0x59: uinput.KEY_KP1,
            0x5A: uinput.KEY_KP2,
            0x5B: uinput.KEY_KP3,
            0x5C: uinput.KEY_KP4,
            0x5D: uinput.KEY_KP5,
            0x5E: uinput.KEY_KP6,
            0x5F: uinput.KEY_KP7,
            0x60: uinput.KEY_KP8,
            0x61: uinput.KEY_KP9,
            0x62: uinput.KEY_KP0,
            0x63: uinput.KEY_KPDOT,
            0x64: uinput.KEY_102ND,
            0xE0: uinput.KEY_LEFTCTRL,
            0xE1: uinput.KEY_LEFTSHIFT,
            0xE2: uinput.KEY_LEFTALT,
            0xE3: uinput.KEY_LEFTMETA,
            0xE4: uinput.KEY_RIGHTCTRL,
            0xE5: uinput.KEY_RIGHTSHIFT,
            0xE6: uinput.KEY_RIGHTALT,
            0xE7: uinput.KEY_RIGHTMETA,
        }

        hid_modifiers = {
            0x01: uinput.KEY_LEFTCTRL,
            0x02: uinput.KEY_LEFTSHIFT,
            0x04: uinput.KEY_LEFTALT,
            0x08: uinput.KEY_LEFTMETA,
            0x10: uinput.KEY_RIGHTCTRL,
            0x20: uinput.KEY_RIGHTSHIFT,
            0x40: uinput.KEY_RIGHTALT,
            0x80: uinput.KEY_RIGHTMETA,
        }

        return hid_to_linux_key, hid_modifiers

    def get_key_to_ascii_table(self) -> dict[tuple[int, int], tuple[str, str]]:
        # HID-style character map for US layout
        key_to_ascii = {
            uinput.KEY_A: ('a', 'A'),
            uinput.KEY_B: ('b', 'B'),
            uinput.KEY_C: ('c', 'C'),
            uinput.KEY_D: ('d', 'D'),
            uinput.KEY_E: ('e', 'E'),
            uinput.KEY_F: ('f', 'F'),
            uinput.KEY_G: ('g', 'G'),
            uinput.KEY_H: ('h', 'H'),
            uinput.KEY_I: ('i', 'I'),
            uinput.KEY_J: ('j', 'J'),
            uinput.KEY_K: ('k', 'K'),
            uinput.KEY_L: ('l', 'L'),
            uinput.KEY_M: ('m', 'M'),
            uinput.KEY_N: ('n', 'N'),
            uinput.KEY_O: ('o', 'O'),
            uinput.KEY_P: ('p', 'P'),
            uinput.KEY_Q: ('q', 'Q'),
            uinput.KEY_R: ('r', 'R'),
            uinput.KEY_S: ('s', 'S'),
            uinput.KEY_T: ('t', 'T'),
            uinput.KEY_U: ('u', 'U'),
            uinput.KEY_V: ('v', 'V'),
            uinput.KEY_W: ('w', 'W'),
            uinput.KEY_X: ('x', 'X'),
            uinput.KEY_Y: ('y', 'Y'),
            uinput.KEY_Z: ('z', 'Z'),

            uinput.KEY_1: ('1', '!'),
            uinput.KEY_2: ('2', '@'),
            uinput.KEY_3: ('3', '#'),
            uinput.KEY_4: ('4', '$'),
            uinput.KEY_5: ('5', '%'),
            uinput.KEY_6: ('6', '^'),
            uinput.KEY_7: ('7', '&'),
            uinput.KEY_8: ('8', '*'),
            uinput.KEY_9: ('9', '('),
            uinput.KEY_0: ('0', ')'),

            uinput.KEY_SPACE: (' ', ' '),
            uinput.KEY_MINUS: ('-', '_'),
            uinput.KEY_EQUAL: ('=', '+'),
            uinput.KEY_LEFTBRACE: ('[', '{'),
            uinput.KEY_RIGHTBRACE: (']', '}'),
            uinput.KEY_BACKSLASH: ('\\', '|'),
            uinput.KEY_SEMICOLON: (';', ':'),
            uinput.KEY_APOSTROPHE: ("'", '"'),
            uinput.KEY_GRAVE: ('`', '~'),
            uinput.KEY_COMMA: (',', '<'),
            uinput.KEY_DOT: ('.', '>'),
            uinput.KEY_SLASH: ('/', '?'),
            uinput.KEY_ENTER: ('\n', '\n'),
            uinput.KEY_TAB: ('\t', '\t'),
            uinput.KEY_BACKSPACE: ('\b', '\b'),
        }

        return key_to_ascii
