# AutoTennisBallRobot — Instruction Manual

## Overview

The AutoTennisBallRobot is a remotely operated robot driven by a Raspberry Pi 3B+. A laptop running an Xbox 360 controller streams motor commands over WiFi at 50 Hz. The robot has a built-in safety watchdog that brakes automatically if communication is lost.

---

## Hardware Requirements

| Component | Details |
|---|---|
| Robot computer | Raspberry Pi 3B+ |
| Motor controllers | REV Spark PWM (one per motor) |
| Motors | CIM motors |
| Controller | Xbox 360 (wired or with USB receiver) |
| Laptop OS | Linux (xpad driver required for Xbox controller) |

GPIO connections on the Pi:
- **GPIO 12** — left motor Spark signal wire
- **GPIO 13** — right motor Spark signal wire

---

## First-Time Setup

### 1. Set Up the Pi's WiFi Hotspot (one-time)

The Pi acts as its own WiFi access point so the laptop can always connect to it at a fixed address regardless of location.

**On the Pi:**
```bash
sudo bash robot/setup_hotspot.sh
sudo reboot
```

Custom SSID and password:
```bash
sudo bash robot/setup_hotspot.sh MyNetwork mypassword
```

After reboot, the Pi broadcasts a WiFi network called **TennisBotAP** and is permanently reachable at **10.0.0.1**.

### 2. Install Controller Dependencies (one-time, on the laptop)

```bash
pip install -r controller/requirements.txt
```

---

## Every Session — Starting the Robot

### Step 1: Power on the Pi
Wait ~30 seconds for it to boot. The `TennisBotAP` network will appear on your laptop.

### Step 2: Connect your laptop to TennisBotAP
- SSID: `TennisBotAP`
- Password: `tennisbot` (unless you customized it)

### Step 3: SSH into the Pi and start the robot server
```bash
ssh pi@10.0.0.1
sudo pigpiod
python3 robot/robot.py
```

You should see:
```
Robot listening on UDP port 5005
Left motor → GPIO 12 | Right motor → GPIO 13
```

### Step 4: Plug in the Xbox controller and start the laptop client
On your laptop:
```bash
python3 controller/controller.py
```

You should see:
```
Controller : Xbox 360 Controller
Robot      : 10.0.0.1:5005
Rate       : 50 Hz
Drive      : tank (left stick = left motor, right stick = right motor)
```

The robot is now live.

---

## Driving

The robot uses **tank drive**:

| Input | Action |
|---|---|
| Left stick up/down | Left motor forward/reverse |
| Right stick up/down | Right motor forward/reverse |
| Both sticks forward | Drive straight forward |
| Sticks in opposite directions | Spin in place |
| Back button (hold) | Emergency stop |

A small deadzone (8% of stick travel) is applied to prevent motor buzz when the stick is at rest.

---

## Stopping

**Normal stop:** Press `Ctrl-C` on the laptop. The controller sends a final stop command before exiting.

**Emergency stop:** Hold the **Back** button on the Xbox controller. Motors go to neutral while held.

**Watchdog stop:** If the laptop disconnects or the program crashes, the robot automatically brakes after **0.5 seconds** with no received packet.

---

## Troubleshooting

**`pigpio daemon not running`**
```bash
sudo pigpiod
```

**`No controller detected`**
Make sure the Xbox 360 controller is plugged in before running `controller.py`. The xpad kernel module must be loaded (`lsmod | grep xpad`).

**Robot drives backward when you push forward**
Edit `robot/robot.py` and set the relevant invert flag:
```python
LEFT_INVERT  = True   # flip left motor
RIGHT_INVERT = True   # flip right motor
```

**Controller axes don't match expected behavior**
The axis indices are set for Linux/xpad. If using a different driver, adjust:
```python
AXIS_LEFT_Y  = 1   # change to match your driver
AXIS_RIGHT_Y = 4
```
Run `python3 -c "import pygame; pygame.init(); pygame.joystick.init(); j=pygame.joystick.Joystick(0); j.init(); [print(i, j.get_axis(i)) for i in range(j.get_numaxes())]"` while moving each stick to identify the correct axis numbers.

**TennisBotAP not appearing**
SSH via ethernet, check `sudo systemctl status hostapd` and `sudo systemctl status dnsmasq`.

---

## Configuration Reference

All tunable constants are at the top of each file — no changes needed elsewhere.

**`robot/robot.py`**

| Constant | Default | Purpose |
|---|---|---|
| `LEFT_PIN` | `12` | GPIO pin for left motor |
| `RIGHT_PIN` | `13` | GPIO pin for right motor |
| `LEFT_INVERT` | `False` | Reverse left motor direction |
| `RIGHT_INVERT` | `False` | Reverse right motor direction |
| `WATCHDOG_TIMEOUT` | `0.5` s | Seconds before auto-brake on packet loss |

**`controller/controller.py`**

| Constant | Default | Purpose |
|---|---|---|
| `SEND_HZ` | `50` | Command packets per second |
| `DEADZONE` | `0.08` | Stick deadzone (fraction of full travel) |
| `AXIS_LEFT_Y` | `1` | pygame axis for left stick Y |
| `AXIS_RIGHT_Y` | `4` | pygame axis for right stick Y |
