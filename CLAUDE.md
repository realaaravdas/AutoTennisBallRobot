# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

Two-process system communicating over UDP:

- **`robot/robot.py`** — runs on the Raspberry Pi 3B+. Binds a UDP socket and translates received throttle values into PWM pulsewidths via `pigpio`. Requires the `pigpiod` daemon (`sudo pigpiod`).
- **`controller/controller.py`** — runs on the laptop. Reads an Xbox 360 controller via `pygame` and streams 8-byte packets (`struct.pack("ff", left, right)`) to the robot at 50 Hz.

Packet format: two 32-bit floats, each in `[-1.0, 1.0]`, representing left and right motor throttle. The robot maps these to PWM pulsewidths `[1000, 2000] µs` (1500 = neutral/brake).

Motor outputs use GPIO 12 (left) and GPIO 13 (right) via `pigpio.set_servo_pulsewidth`. The watchdog in `robot.py` stops motors if no packet arrives within 0.5 s.

## Running

**On the Pi:**
```bash
sudo pigpiod
python3 robot/robot.py
```

**On the laptop** (both devices on the same LAN):
```bash
pip install -r controller/requirements.txt
python3 controller/controller.py <robot-ip>   # e.g. 192.168.1.50
```

## Static IP setup (one-time, on the Pi)

The Pi connects to an existing router as a normal WiFi client with a fixed IP — no hotspot is created.

1. Configure WiFi credentials (if not already done):
   ```bash
   sudo raspi-config   # System Options → Wireless LAN
   ```
2. Assign the static IP:
   ```bash
   sudo bash robot/setup_static_ip.sh <static_ip> <router_ip> [interface]
   # e.g.: sudo bash robot/setup_static_ip.sh 192.168.1.50 192.168.1.1
   sudo reboot
   ```

After reboot the Pi joins the LAN at the address you chose.

## Key constants

| File | Constant | Default | Purpose |
|---|---|---|---|
| `robot.py` | `LEFT_PIN` / `RIGHT_PIN` | 12 / 13 | GPIO PWM pins |
| `robot.py` | `LEFT_INVERT` / `RIGHT_INVERT` | `False` | Flip motor direction |
| `robot.py` | `WATCHDOG_TIMEOUT` | 0.5 s | Safety stop delay |
| `controller.py` | `SEND_HZ` | 50 | Packet rate |
| `controller.py` | `DEADZONE` | 0.08 | Stick deadzone |
| `controller.py` | `AXIS_LEFT_Y` / `AXIS_RIGHT_Y` | 1 / 4 | pygame axis indices (Linux/xpad) |
