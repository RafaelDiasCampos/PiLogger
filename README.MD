# PiLogger

Hardware keyboard logger using a Raspberry Pi Pico + Raspberry Pi Zero 2W

## Features

- Clone vendorId and productId from the connected keyboard to the target machine.
- Forward all keystrokes to the target machine.
- Log pressed keystrokes.
- Forward LED states (Capslock, Numlock, Scrolllock) to keyboard.

## How to use

### Configuring Raspberry Pi Pico

The code for the Pi Pico can be built using the Arduino IDE using the following procedure:

- Add the URL and install the package for the RP2040 boards:

```
https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
```

- Install the Adafruit TinyUSB library
- Select your RP2040 board and change the USB Stack to "Adafruit TinyUSB Host (native)"
- Compile and flash the code to the board

You can check if the Pico is working by connecting a UART reader to Serial1 (GP0 TX and GP1 RX, Baud Rate 115200) and check the messages sent when connecting a USB keyboard to the board.

### Configuring Raspberry Pi Zero 2W

The Pi Zero 2W has to be configured to act as a USB Gadget device.

- Edit the file `/boot/firmware/config.txt` and add the following lines at the end:

```
enable_uart=1
dtoverlay=dwc2,dr_mode=peripheral
```

- Add the required modules to `/etc/modules`:
```
libcomposite
dwc2
uinput
```

- Clone the repository, create a venv and install the required packages:
```bash
git clone https://github.com/RafaelDiasCampos/PiLogger.git
cd PiLogger
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Connecting the Raspberry Pi devices

The Pi Pico uses the Serial1 port to send and receive data.
Connect it to the Raspberry Pi Zero 2W like this:

```
Pico GP0 (TX)   ->   Zero 2W GPIO 15 (UART RX)
Pico GP1 (RX)   ->   Zero 2W GPIO 14 (UART TX)
Pico GND        ->   Any Zero 2W GND pin
Pico 5V         ->   Any Zero 2W 5V pin
```

### Starting the keylogger

To start the keylogger, run the `Zero2W Logger/main.py` as root.
After connecting a keyboard to the Pi Pico you should see the pressed keys logged in the `keyboard_log.raw` and `keyboard_log.txt` files.

## How it works

TODO

