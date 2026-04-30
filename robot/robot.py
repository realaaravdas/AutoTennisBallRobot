#!/usr/bin/env python3
"""
Robot-side server. Run on the Raspberry Pi 3B+.
Requires pigpio daemon: sudo pigpiod

Usage: python3 robot.py [--port 5005]
"""

import pigpio
import socket
import struct
import signal
import sys
import time
import argparse

LEFT_PIN = 12
RIGHT_PIN = 13

NEUTRAL_PW = 1500   # microseconds — stopped/brake
MIN_PW     = 1000   # full reverse
MAX_PW     = 2000   # full forward

# If the robot drives backwards when you push forward, flip the sign for that motor here.
LEFT_INVERT  = False
RIGHT_INVERT = False

WATCHDOG_TIMEOUT = 0.5   # seconds without a packet → stop motors


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def throttle_to_pw(throttle):
    """Map [-1.0, 1.0] to [1000, 2000] microseconds."""
    return int(NEUTRAL_PW + clamp(throttle, -1.0, 1.0) * 500)


class Robot:
    def __init__(self, port):
        self.port = port
        self.pi = pigpio.pi()
        if not self.pi.connected:
            sys.exit("pigpio daemon not running — start it with: sudo pigpiod")

        self.stop()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", port))
        self.sock.settimeout(WATCHDOG_TIMEOUT)

        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def stop(self):
        self.pi.set_servo_pulsewidth(LEFT_PIN,  NEUTRAL_PW)
        self.pi.set_servo_pulsewidth(RIGHT_PIN, NEUTRAL_PW)

    def set_motors(self, left, right):
        if LEFT_INVERT:
            left = -left
        if RIGHT_INVERT:
            right = -right
        self.pi.set_servo_pulsewidth(LEFT_PIN,  throttle_to_pw(left))
        self.pi.set_servo_pulsewidth(RIGHT_PIN, throttle_to_pw(right))

    def run(self):
        print(f"Robot listening on UDP port {self.port}")
        print(f"Left motor → GPIO {LEFT_PIN} | Right motor → GPIO {RIGHT_PIN}")

        while True:
            try:
                data, addr = self.sock.recvfrom(8)
                if len(data) == 8:
                    left, right = struct.unpack("ff", data)
                    self.set_motors(left, right)
            except socket.timeout:
                # Watchdog: no packet received within timeout — safe stop
                self.stop()

    def _shutdown(self, sig, frame):
        print("\nShutting down...")
        self.stop()
        time.sleep(0.1)
        self.pi.stop()
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5005)
    args = parser.parse_args()

    Robot(args.port).run()
