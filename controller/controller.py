#!/usr/bin/env python3
"""
Controller-side client. Run on your laptop/desktop.
Reads an Xbox 360 controller and streams commands to the robot over UDP.

Usage: python3 controller.py <robot_ip> [--port 5005]

Controls (tank drive):
  Left stick Y  → left motor
  Right stick Y → right motor
  Back button   → emergency stop (hold)
"""

import pygame
import socket
import struct
import time
import sys
import argparse

SEND_HZ      = 50        # packets per second
DEADZONE     = 0.08      # ignore stick deflections smaller than this

# Xbox 360 axis indices (Linux/xpad driver)
AXIS_LEFT_Y  = 1
AXIS_RIGHT_Y = 4


def deadzone(value, threshold=DEADZONE):
    if abs(value) < threshold:
        return 0.0
    # rescale so the output starts at 0 right at the deadzone edge
    sign = 1 if value > 0 else -1
    return sign * (abs(value) - threshold) / (1.0 - threshold)


def find_controller():
    count = pygame.joystick.get_count()
    if count == 0:
        return None
    # Prefer Xbox-named device; fall back to first available
    for i in range(count):
        j = pygame.joystick.Joystick(i)
        if "xbox" in j.get_name().lower() or "360" in j.get_name().lower():
            return j
    return pygame.joystick.Joystick(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("robot_ip", help="IP address of the Raspberry Pi")
    parser.add_argument("--port", type=int, default=5005)
    args = parser.parse_args()

    pygame.init()
    pygame.joystick.init()

    joy = find_controller()
    if joy is None:
        sys.exit("No controller detected. Plug in the Xbox 360 controller and retry.")
    joy.init()
    print(f"Controller : {joy.get_name()}")
    print(f"Robot      : {args.robot_ip}:{args.port}")
    print(f"Rate       : {SEND_HZ} Hz")
    print("Drive      : tank (left stick = left motor, right stick = right motor)")
    print("Press Ctrl-C to quit\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.robot_ip, args.port)
    interval = 1.0 / SEND_HZ

    try:
        while True:
            t_start = time.monotonic()

            pygame.event.pump()

            # Check for controller disconnect
            if pygame.joystick.get_count() == 0:
                print("Controller disconnected — sending stop")
                sock.sendto(struct.pack("ff", 0.0, 0.0), dest)
                time.sleep(1.0)
                continue

            # Back button (button 6) = emergency stop
            e_stop = joy.get_button(6)
            if e_stop:
                left, right = 0.0, 0.0
            else:
                # Pygame Y axis is inverted: up = -1, so negate
                left  = -deadzone(joy.get_axis(AXIS_LEFT_Y))
                right = -deadzone(joy.get_axis(AXIS_RIGHT_Y))

            sock.sendto(struct.pack("ff", left, right), dest)

            elapsed = time.monotonic() - t_start
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    except KeyboardInterrupt:
        print("\nSending stop command...")
        sock.sendto(struct.pack("ff", 0.0, 0.0), dest)
        time.sleep(0.1)

    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
