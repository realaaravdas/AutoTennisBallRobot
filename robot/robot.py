#!/usr/bin/env python3
"""
Autonomous tennis-ball collecting robot.
Vision : OAK-D-Lite (Myriad X NPU) — YOLOv5n-COCO "sports ball" class.
Motors : REV Spark PWM via pigpio on Raspberry Pi 3B+.

Run on the Pi:
    sudo pigpiod
    python3 robot/robot.py
"""

import pigpio
import depthai as dai
import blobconverter
import signal
import sys
import time
import random

# ── GPIO / PWM ────────────────────────────────────────────────────────────────
LEFT_PIN   = 12
RIGHT_PIN  = 13
NEUTRAL_PW = 1500
LEFT_INVERT  = False
RIGHT_INVERT = False

# ── Speed ─────────────────────────────────────────────────────────────────────
MAX_SPEED  = 0.50   # hard cap — never exceed half throttle
STEER_GAIN = 0.80   # how hard to turn toward the ball (0 = straight, 1 = max diff)

# ── Vision ────────────────────────────────────────────────────────────────────
NN_WIDTH  = 416
NN_HEIGHT = 416
SPORTS_BALL_CLASS = 32   # COCO-80 index for "sports ball" (covers tennis balls)
CONF_THRESH       = 0.40  # minimum detection confidence

# YOLOv5n standard anchors for 416×416 input
YOLO_ANCHORS = [
    10, 13, 16, 30, 33, 23,       # P3/8  → 52×52 feature map
    30, 61, 62, 45, 59, 119,      # P4/16 → 26×26
    116, 90, 156, 198, 373, 326,  # P5/32 → 13×13
]
YOLO_ANCHOR_MASKS = {
    "side52": [0, 1, 2],
    "side26": [3, 4, 5],
    "side13": [6, 7, 8],
}

# ── Seek (wander) parameters ──────────────────────────────────────────────────
SEEK_FORWARD_SECS = 2.5   # drive straight for this long before turning
SEEK_TURN_SECS    = 1.2   # then turn for this long
SEEK_SPEED        = 0.35  # forward throttle while seeking
SEEK_INNER_SPEED  = 0.08  # inner-wheel throttle during a seek turn


# ── Motor control ─────────────────────────────────────────────────────────────

def _throttle_to_pw(throttle):
    return int(NEUTRAL_PW + max(-1.0, min(1.0, throttle)) * 500)


class Motors:
    def __init__(self):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            sys.exit("pigpio daemon not running — start with: sudo pigpiod")
        self._neutral()
        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def set(self, left, right):
        l = -left  if LEFT_INVERT  else left
        r = -right if RIGHT_INVERT else right
        self.pi.set_servo_pulsewidth(LEFT_PIN,  _throttle_to_pw(l))
        self.pi.set_servo_pulsewidth(RIGHT_PIN, _throttle_to_pw(r))

    def _neutral(self):
        self.pi.set_servo_pulsewidth(LEFT_PIN,  NEUTRAL_PW)
        self.pi.set_servo_pulsewidth(RIGHT_PIN, NEUTRAL_PW)

    def _shutdown(self, sig, frame):
        print("\nShutting down...")
        self._neutral()
        time.sleep(0.1)
        self.pi.stop()
        sys.exit(0)


# ── Seek state machine ────────────────────────────────────────────────────────

class Seeker:
    """
    Alternates between straight-forward bursts and random turns so the robot
    sweeps the area looking for tennis balls.
    """
    def __init__(self):
        self._phase    = "forward"
        self._deadline = time.monotonic() + SEEK_FORWARD_SECS
        self._turn_dir = 1   # +1 = right, -1 = left

    def command(self):
        """Return (left, right) throttle for current seek phase."""
        now = time.monotonic()
        if now >= self._deadline:
            if self._phase == "forward":
                self._phase    = "turn"
                self._deadline = now + SEEK_TURN_SECS
                self._turn_dir = random.choice([-1, 1])
            else:
                self._phase    = "forward"
                self._deadline = now + SEEK_FORWARD_SECS

        if self._phase == "forward":
            return SEEK_SPEED, SEEK_SPEED

        # Turn: outer wheel at SEEK_SPEED, inner at SEEK_INNER_SPEED
        if self._turn_dir == 1:    # turn right → right wheel is inner
            return SEEK_SPEED, SEEK_INNER_SPEED
        else:                       # turn left → left wheel is inner
            return SEEK_INNER_SPEED, SEEK_SPEED


# ── OAK-D-Lite pipeline ───────────────────────────────────────────────────────

def build_pipeline(blob_path):
    pipeline = dai.Pipeline()

    cam = pipeline.create(dai.node.ColorCamera)
    cam.setPreviewSize(NN_WIDTH, NN_HEIGHT)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setFps(30)

    nn = pipeline.create(dai.node.YoloDetectionNetwork)
    nn.setBlobPath(blob_path)
    nn.setConfidenceThreshold(CONF_THRESH)
    nn.setNumClasses(80)
    nn.setCoordinateSize(4)
    nn.setAnchors(YOLO_ANCHORS)
    nn.setAnchorMasks(YOLO_ANCHOR_MASKS)
    nn.setIouThreshold(0.5)
    nn.setNumInferenceThreads(2)
    nn.input.setBlocking(False)
    nn.input.setQueueSize(1)

    cam.preview.link(nn.input)

    xout = pipeline.create(dai.node.XLinkOut)
    xout.setStreamName("detections")
    nn.out.link(xout.input)

    return pipeline


def best_ball(detections):
    """
    From all sports-ball detections return the largest by bounding-box area
    (biggest = closest, most worth chasing). Returns None if none found.
    """
    balls = [d for d in detections if d.label == SPORTS_BALL_CLASS]
    if not balls:
        return None
    return max(balls, key=lambda d: (d.xmax - d.xmin) * (d.ymax - d.ymin))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading YOLOv5n-COCO blob (first run downloads ~10 MB)...")
    blob_path = blobconverter.from_zoo(
        "yolov5n_coco_416x416",
        shaves=6,
        zoo_type="depthai",
    )
    print(f"Blob ready: {blob_path}")

    motors = Motors()
    seeker = Seeker()

    print("Arming ESCs (2 s at neutral)...")
    time.sleep(2.0)

    pipeline = build_pipeline(blob_path)
    print("Starting OAK-D-Lite pipeline...\n")

    with dai.Device(pipeline) as device:
        q = device.getOutputQueue("detections", maxSize=1, blocking=False)
        print("Running. Ctrl-C to stop.\n")

        while True:
            pkt = q.tryGet()
            detections = pkt.detections if pkt is not None else []

            ball = best_ball(detections)

            if ball is not None:
                # Horizontal center of ball, normalised to [-0.5, +0.5]
                # Positive → ball is right of frame center → steer right
                cx = (ball.xmin + ball.xmax) / 2.0 - 0.5

                left  = max(-MAX_SPEED, min(MAX_SPEED, MAX_SPEED + cx * STEER_GAIN))
                right = max(-MAX_SPEED, min(MAX_SPEED, MAX_SPEED - cx * STEER_GAIN))

                motors.set(left, right)
                conf = ball.confidence
                print(f"CHASE  conf={conf:.0%}  cx={cx:+.2f}  L={left:.2f}  R={right:.2f}    ", end="\r")
            else:
                left, right = seeker.command()
                motors.set(left, right)
                print(f"SEEK   L={left:.2f}  R={right:.2f}                          ", end="\r")

            time.sleep(0.02)   # 50 Hz control loop


if __name__ == "__main__":
    main()
