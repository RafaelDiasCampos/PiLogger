#include "Adafruit_TinyUSB.h"
#include "tusb.h"

// Language ID: English
#define LANGUAGE_ID 0x0409

// Timeout for the watchdog
#define WATCHDOG_TIMEOUT_MS 500  // 0.5 seconds

typedef struct {
  tusb_desc_device_t desc_device;
  uint16_t manufacturer[32];
  uint16_t product[48];
  uint16_t serial[16];
  bool mounted;
} dev_info_t;

// CFG_TUH_DEVICE_MAX is defined by tusb_config header
dev_info_t dev_info[CFG_TUH_DEVICE_MAX] = { 0 };

// Keyboard Address and Instance ID
uint8_t keyboard_addr = 0;
uint8_t keyboard_inst = 0;

// Enable TinyUSB host support
#ifndef USE_TINYUSB_HOST
#error "This example requires TinyUSB host mode. Set Tools -> USB Stack -> Adafruit TinyUSB Host"
#endif

Adafruit_USBH_Host USBHost;

//--------------------------------------------------------------------+
// Setup & Loop
//--------------------------------------------------------------------+

void setup() {
  Serial1.begin(115200);
  while (!Serial1) delay(10);

  Serial1.println("[*] Pico USB Host: Keyboard HID Report Reader");

  watchdog_enable(WATCHDOG_TIMEOUT_MS, 1);

  if (!USBHost.begin(0)) {
    Serial1.println("[-] USBHost.begin() failed");
  } else {
    Serial1.println("[+] USB Host initialized");
  }
}


void loop() {
  watchdog_update();
  handle_serial();
  // Process USB tasks
  USBHost.task();
  Serial1.flush();
}

//--------------------------------------------------------------------+
// Helper functions
//--------------------------------------------------------------------+

void handle_serial() {
  if (Serial1.available()) {
    uint8_t byte_read = Serial1.read();

    Serial1.printf("[+] Received Byte: 0x%02X\n", byte_read);

    if (byte_read == 0xFF) {
      Serial1.println("[*] Resetting USB stack.");
      tuh_deinit(0);
      tuh_init(0);
      return;
    }

    static uint8_t led_report;
    led_report = byte_read & 0x1F;

    if (tuh_hid_set_report(keyboard_addr, keyboard_inst, 1, HID_REPORT_TYPE_OUTPUT, &led_report, 1)) {
      Serial1.println("[+] LED report sent");
    } else {
      Serial1.println("[-] LED report failed");
    }
  }
}

//--------------------------------------------------------------------+
// TinyUSB HID Callbacks
//--------------------------------------------------------------------+

// Called when a device is mounted
extern "C" void tuh_mount_cb(uint8_t dev_addr) {
  Serial1.printf("[+] Device mounted: address = %u\n", dev_addr);

  dev_info_t *dev = &dev_info[dev_addr - 1];
  dev->mounted = true;

  // Get Device Descriptor
  tuh_descriptor_get_device(dev_addr, &dev->desc_device, 18, print_device_descriptor, 0);
}

// Called when a device is umounted
extern "C" void tuh_umount_cb(uint8_t dev_addr) {
  Serial1.printf("[-] USB device removed: address = %u\r\n", dev_addr);
}

// Called when an HID device is mounted
extern "C" void tuh_hid_mount_cb(uint8_t dev_addr, uint8_t instance,
                                 uint8_t const *desc_report, uint16_t desc_len) {
  Serial1.printf("[+] HID device mounted: addr=%u, instance=%u, desc_len=%u\n", dev_addr, instance, desc_len);

  // Identify if it's a keyboard
  if (tuh_hid_interface_protocol(dev_addr, instance) == HID_ITF_PROTOCOL_KEYBOARD) {
    Serial1.println("[+] HID keyboard detected");

    keyboard_addr = dev_addr;
    keyboard_inst = instance;

    tuh_hid_receive_report(dev_addr, instance);
  }
}


// Called when an HID device is umounted
extern "C" void tuh_hid_umount_cb(uint8_t dev_addr, uint8_t instance) {
  Serial1.printf("[-] HID device removed: addr=%u, instance=%u\r\n", dev_addr, instance);
}

// Called when an HID report is received
extern "C" void tuh_hid_report_received_cb(uint8_t dev_addr, uint8_t instance,
                                           uint8_t const *report, uint16_t len) {
  if (tuh_hid_interface_protocol(dev_addr, instance) == HID_ITF_PROTOCOL_KEYBOARD) {
    Serial1.printf("[+] Keyboard report [mod=0x%02X]: ", report[0]);
    for (int i = 2; i < 8; ++i) {
      if (report[i] != 0) Serial1.printf("0x%02X ", report[i]);
    }
    Serial1.println();

    // Keep polling
    tuh_hid_receive_report(dev_addr, instance);
  } else {
    Serial1.printf("[-] Non-keyboard HID report (len=%d)\n", len);
  }
}

// Called when a keyboard report is received
extern "C" void tuh_hid_keyboard_isr(uint8_t dev_addr, uint8_t const *report, uint16_t len) {
  // HID report: [modifiers, reserved, key1, key2, key3, key4, key5, key6]
  Serial1.printf("[+] HID report [mod=0x%02X]: ", report[0]);

  for (int i = 2; i < 8; ++i) {
    if (report[i] != 0) {
      Serial1.printf("0x%02X ", report[i]);
    }
  }

  Serial1.println();

  // Optionally forward raw HID report over UART
  // Serial1.write(report, 8);  // Uncomment to send over UART
}

//--------------------------------------------------------------------+
// String Descriptor Helper
//--------------------------------------------------------------------+

void print_device_descriptor(tuh_xfer_t *xfer) {
  if (XFER_RESULT_SUCCESS != xfer->result) {
    Serial1.printf("[-] Failed to get device descriptor\r\n");
    return;
  }

  uint8_t const daddr = xfer->daddr;
  dev_info_t *dev = &dev_info[daddr - 1];
  tusb_desc_device_t *desc = &dev->desc_device;

  const char *manu = "";
  const char *prod = "";
  const char *serial = "";

  // Log the descriptor indices for debugging
  Serial1.printf("[+] Descriptor indices: iManufacturer=%d, iProduct=%d, iSerialNumber=%d\r\n",
                 desc->iManufacturer, desc->iProduct, desc->iSerialNumber);

  // Try to get Manufacturer String
  if (desc->iManufacturer) {
    Serial1.printf("[+] Attempting to get Manufacturer string...\r\n");
    if (tuh_descriptor_get_manufacturer_string_sync(daddr, LANGUAGE_ID,
                                                    dev->manufacturer,
                                                    sizeof(dev->manufacturer))
        == XFER_RESULT_SUCCESS) {
      utf16_to_utf8(dev->manufacturer, sizeof(dev->manufacturer));
      manu = (char *)dev->manufacturer;
    } else {
      Serial1.printf("[-] Failed to retrieve Manufacturer string\r\n");
    }
  }

  // Try to get Product String
  if (desc->iProduct) {
    Serial1.printf("[+] Attempting to get Product string...\r\n");
    if (tuh_descriptor_get_product_string_sync(daddr, LANGUAGE_ID,
                                               dev->product,
                                               sizeof(dev->product))
        == XFER_RESULT_SUCCESS) {
      utf16_to_utf8(dev->product, sizeof(dev->product));
      prod = (char *)dev->product;
    } else {
      Serial1.printf("[-] Failed to retrieve Product string\r\n");
    }
  }

  // Try to get Serial Number String
  if (desc->iSerialNumber) {
    Serial1.printf("[+] Attempting to get Serial Number string...\r\n");
    if (tuh_descriptor_get_serial_string_sync(daddr, LANGUAGE_ID,
                                              dev->serial,
                                              sizeof(dev->serial))
        == XFER_RESULT_SUCCESS) {
      utf16_to_utf8(dev->serial, sizeof(dev->serial));
      serial = (char *)dev->serial;
    } else {
      Serial1.printf("[-] Failed to retrieve Serial Number string\r\n");
    }
  }

  // Print everything in a single line
  Serial1.printf("[+] DeviceInfo: VID=%04X PID=%04X MANU=\"%s\" PROD=\"%s\" SERIAL=\"%s\"\r\n",
                 desc->idVendor,
                 desc->idProduct,
                 manu,
                 prod,
                 serial);
}

static void _convert_utf16le_to_utf8(const uint16_t *utf16, size_t utf16_len, uint8_t *utf8, size_t utf8_len) {
  // TODO: Check for runover.
  (void)utf8_len;
  // Get the UTF-16 length out of the data itself.

  for (size_t i = 0; i < utf16_len; i++) {
    uint16_t chr = utf16[i];
    if (chr < 0x80) {
      *utf8++ = chr & 0xff;
    } else if (chr < 0x800) {
      *utf8++ = (uint8_t)(0xC0 | (chr >> 6 & 0x1F));
      *utf8++ = (uint8_t)(0x80 | (chr >> 0 & 0x3F));
    } else {
      // TODO: Verify surrogate.
      *utf8++ = (uint8_t)(0xE0 | (chr >> 12 & 0x0F));
      *utf8++ = (uint8_t)(0x80 | (chr >> 6 & 0x3F));
      *utf8++ = (uint8_t)(0x80 | (chr >> 0 & 0x3F));
    }
    // TODO: Handle UTF-16 code points that take two entries.
  }
}

// Count how many bytes a utf-16-le encoded string will take in utf-8.
static int _count_utf8_bytes(const uint16_t *buf, size_t len) {
  size_t total_bytes = 0;
  for (size_t i = 0; i < len; i++) {
    uint16_t chr = buf[i];
    if (chr < 0x80) {
      total_bytes += 1;
    } else if (chr < 0x800) {
      total_bytes += 2;
    } else {
      total_bytes += 3;
    }
    // TODO: Handle UTF-16 code points that take two entries.
  }
  return total_bytes;
}

void utf16_to_utf8(uint16_t *temp_buf, size_t buf_len) {
  size_t utf16_len = ((temp_buf[0] & 0xff) - 2) / sizeof(uint16_t);
  size_t utf8_len = _count_utf8_bytes(temp_buf + 1, utf16_len);

  _convert_utf16le_to_utf8(temp_buf + 1, utf16_len, (uint8_t *)temp_buf, buf_len);
  ((uint8_t *)temp_buf)[utf8_len] = '\0';
}
