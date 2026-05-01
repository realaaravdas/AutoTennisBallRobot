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

**On the laptop** (connect to `TennisBotAP` WiFi first):
```bash
pip install -r controller/requirements.txt
python3 controller/controller.py           # defaults to 10.0.0.1
python3 controller/controller.py <ip>      # override IP if needed
```

## Hotspot setup (one-time, on the Pi)

```bash
sudo bash robot/setup_hotspot.sh [ssid] [password]
sudo reboot
```

After reboot the Pi broadcasts its own WiFi (`TennisBotAP` / `tennisbot` by default) and is always reachable at `10.0.0.1`.

## Key constants

| File | Constant | Default | Purpose |
|---|---|---|---|
| `robot.py` | `LEFT_PIN` / `RIGHT_PIN` | 12 / 13 | GPIO PWM pins |
| `robot.py` | `LEFT_INVERT` / `RIGHT_INVERT` | `False` | Flip motor direction |
| `robot.py` | `WATCHDOG_TIMEOUT` | 0.5 s | Safety stop delay |
| `controller.py` | `SEND_HZ` | 50 | Packet rate |
| `controller.py` | `DEADZONE` | 0.08 | Stick deadzone |
| `controller.py` | `AXIS_LEFT_Y` / `AXIS_RIGHT_Y` | 1 / 4 | pygame axis indices (Linux/xpad) |
