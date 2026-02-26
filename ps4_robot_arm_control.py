"""
PS4 Controller → Robotic Arm Control
====================================

Real-time robotic arm control using a PS4 controller.

• Left stick  → Move X/Y
• Right stick Y → Move Z
• Right stick X → Control gripper
• Circle button → EMERGENCY KILL (Torque OFF)

Author: Dean Zylman
Project: Z-Robotics
"""

import pygame
import serial
import json
import time

# ============================================================
# ========================= USER CONFIG ======================
# ============================================================

SERIAL_PORT = "/dev/tty.usbserial-10"   # ⬅️ set to your USB port

BAUDRATE = 115200

UPDATE_HZ = 30
POS_STEP = 6.0
Z_STEP = 5.0

# Gripper angles (radians)
GRIPPER_OPEN = 3.14
GRIPPER_CLOSED = 1.08
GRIPPER_STEP = 0.04


# ============================================================
# ============================================================
# ================= WORKSPACE LIMITS =========================
# ============================================================

# These define the allowed movement boundaries (in millimeters)
# These values are in MILLIMETERS
# They are measured from the robot's origin (0,0,0)
#
# Example:
# X = 220 means 22 cm forward
# Y = -250 means 25 cm to the left
# Z = 200 means 20 cm up

X_MIN, X_MAX = 50, 400
Y_MIN, Y_MAX = -250, 250
Z_MIN, Z_MAX = -150, 300

# ================= SAFE START POSITION ======================
# ============================================================

# These values are in MILLIMETERS
# They are measured from the robot's origin (0,0,0)

x, y, z = 220, 0, 200
t = GRIPPER_OPEN


# ============================================================
# ================= SERIAL SETUP =============================
# ============================================================

ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.01)
ser.setRTS(False)
ser.setDTR(False)
time.sleep(2)


def send(cmd):
    """
    Send JSON command to robotic arm.
    """
    msg = json.dumps(cmd)
    ser.write((msg + "\n").encode("utf-8"))


# ============================================================
# ================= INIT ROBOT ===============================
# ============================================================

send({"T": 210, "cmd": 1})  # Torque ON at startup
time.sleep(0.3)


# ============================================================
# ================= PYGAME INIT ==============================
# ============================================================

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise RuntimeError("No PS4 controller detected")

js = pygame.joystick.Joystick(0)
js.init()

print("Controller detected:", js.get_name())
print("Move sticks or press buttons to see input changes.\n")

clock = pygame.time.Clock()


def dz(v, deadzone=0.12):
    """
    Deadzone filter to remove joystick noise.
    """
    return 0 if abs(v) < deadzone else v


previous_axes = {}
previous_buttons = {}


# ============================================================
# ================= MAIN LOOP ================================
# ============================================================

while True:
    pygame.event.pump()

    # ================= AXES =================

    lx = dz(js.get_axis(0))        # Left stick X
    ly = dz(-js.get_axis(1))       # Left stick Y
    rx = dz(js.get_axis(2))        # Right stick X (gripper)
    ry = dz(-js.get_axis(3))       # Right stick Y (Z)

    axes = {0: lx, 1: ly, 2: rx, 3: ry}

    for i, value in axes.items():
        rounded = round(value, 2)
        if previous_axes.get(i) != rounded:
            print(f"AXIS {i} → {rounded}")
            previous_axes[i] = rounded

    # ================= BUTTONS =================

    for i in range(js.get_numbuttons()):
        state = js.get_button(i)

        if previous_buttons.get(i) != state:
            if state:
                print(f"BUTTON {i} PRESSED")
            else:
                print(f"BUTTON {i} RELEASED")

            previous_buttons[i] = state

        # ================= KILL SWITCH =================
        # Circle button (macOS mapping = button 1)
        # Immediately disables torque

        if i == 1 and state:
            print("!!! EMERGENCY STOP ACTIVATED !!!")
            send({"T": 210, "cmd": 0})  # Torque OFF

    # ========================================================
    # ================= POSITION UPDATE =======================
    # ========================================================

    x += ly * POS_STEP
    y -= lx * POS_STEP
    z += ry * Z_STEP

    x = max(X_MIN, min(X_MAX, x))
    y = max(Y_MIN, min(Y_MAX, y))
    z = max(Z_MIN, min(Z_MAX, z))

    # ========================================================
    # ================= GRIPPER CONTROL =======================
    # ========================================================

    if rx != 0:
        t -= rx * GRIPPER_STEP

    t = max(GRIPPER_CLOSED, min(GRIPPER_OPEN, t))

    # ========================================================
    # ================= SEND COMMAND ==========================
    # ========================================================

    send({
        "T": 1041,
        "x": round(x, 1),
        "y": round(y, 1),
        "z": round(z, 1),
        "t": round(t, 3)
    })

    clock.tick(UPDATE_HZ)
