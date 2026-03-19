# miklat-alert

Visual alert indicator for the Israeli Home Front Command (Pikud HaOref) Red Alert system, built for **Raspberry Pi Zero** with a WS2812B (NeoPixel) LED strip.

The script polls the official alert API and drives a NeoPixel strip to show the current status at a glance:

| Color  | Meaning |
|--------|---------|
| 🔵 Blue   | System starting up / self-test |
| 🔴 Red    | Active alert (rocket / hostile aircraft) |
| 🟠 Orange | Pre-alert ("in the coming minutes") |
| 🟢 Green  | Alert released – turns off automatically after 5 minutes |
| ⚫ Off    | Idle / no active alert |

---

## Hardware Requirements

- Raspberry Pi Zero (W / WH / 2 W)
- WS2812B (NeoPixel) LED strip – 15 LEDs (configurable in code)
- 330 Ω resistor (placed on the data line)
- 5 V power supply adequate for the strip (each LED draws ≈ 60 mA at full white)
- Jumper wires

---

## Wiring Diagram

```
              Raspberry Pi Zero
             ┌──────────────────┐
             │                  │
             │  GPIO 18 (PWM)   │── 330 Ω ──┐
             │                  │            │
             │  GND             │──────┐     │
             └──────────────────┘      │     │
                                       │     │
              WS2812B LED Strip        │     │
             ┌──────────────────┐      │     │
             │  DIN  ───────────│──────┘─────┘
             │  GND  ───────────│──────┘
             │  +5V  ───────────│── 5 V Power Supply (+)
             │                  │
             └──────────────────┘
                                 GND of Pi and Power Supply
                                 must be connected together
```

> **Note:** The 330 Ω resistor is placed between **GPIO 18** and the strip **DIN** (data-in) pin to protect the data line from voltage spikes.  
> If your strip has more than ~30 LEDs, power it from an external 5 V supply and connect the ground to the Pi's GND.

---

## Software Installation

### 1. Prepare the Pi Zero

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip git
```

### 2. Clone the repository

```bash
sudo git clone https://github.com/t0mer/miklat-alert.git /opt/redalert
cd /opt/redalert
```

### 3. Install Python dependencies

```bash
sudo pip3 install -r requirements.txt
```

This installs:

- `rpi_ws281x` – low-level WS281x LED driver
- `adafruit-circuitpython-neopixel` – NeoPixel high-level library
- `adafruit-blinka` – CircuitPython compatibility layer for Raspberry Pi
- `loguru` – structured logging

### 4. Enable SPI (if needed) and set GPU memory

Some WS281x configurations require SPI or a minimum GPU memory split:

```bash
sudo raspi-config
# Interface Options → SPI → Enable
# Performance Options → GPU Memory → set to at least 16
```

Reboot after changes:

```bash
sudo reboot
```

---

## Configuration

The script reads configuration from **environment variables**:

| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_LOCATION` | *(empty – all locations)* | Hebrew city/area name to filter alerts for (e.g. `רעננה`) |
| `MAX_IDS` | `1000` | Number of alert IDs to keep before clearing the seen list |


Set them in the systemd service file or export before running:

```bash
export TARGET_LOCATION="רעננה"
```

### LED Strip Parameters (in code)

| Constant | Default | Description |
|----------|---------|-------------|
| `LED_COUNT` | `15` | Number of LEDs on the strip |
| `LED_PIN` | `18` | GPIO pin (must support PWM – GPIO 18 recommended) |
| `LED_BRIGHTNESS` | `65` | Brightness 0-255 |
| `LED_DMA` | `10` | DMA channel |

---

## Running

### Manual test

```bash
sudo python3 /opt/redalert/redalert.py
```

> `sudo` is required because the WS281x library needs root access to the GPIO/PWM hardware.

### Install as a systemd service

Copy the provided service file and enable it:

```bash
sudo cp /opt/redalert/redalert.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable redalert.service
sudo systemctl start redalert.service
```

Check status:

```bash
sudo systemctl status redalert.service
```

View logs:

```bash
sudo journalctl -u redalert.service -f
```

---

## Service File Reference

The included `redalert.service` runs the script as root, restarts on failure, and waits for network connectivity:

```ini
[Unit]
Description=Red Alert
After=network-online.target
Wants=network-online.target systemd-networkd-wait-online.service

[Service]
KillSignal=SIGINT
WorkingDirectory=/opt/redalert
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/redalert/redalert.py
Restart=always

[Install]
WantedBy=multi-user.target
```

To filter for a specific location, add an `Environment` line under `[Service]`:

```ini
Environment="TARGET_LOCATION=רעננה"
```

---

## License

See [LICENSE](LICENSE) for details.
