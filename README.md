# RoArm-Ps4-Controller
Control a WaveShare RoArm‑M2‑S robotic arm with a PS4 controller using Python and JSON over serial.

PS4 Controller Robot Arm Control
=================================

This project allows you to control a robotic arm using a PS4 controller over USB.

The script:
- Moves the robotic arm in real time
- Prints controller inputs ONLY when they change
- Makes remapping buttons easy
- Is designed to be clean and beginner-friendly


--------------------------------------------------
1️⃣ INSTALL DEPENDENCIES
--------------------------------------------------

You need Python 3.9+

Install pygame:

WINDOWS:
    pip install pygame pyserial

LINUX:
    sudo apt install python3-pip
    pip3 install pygame pyserial

MACOS (Homebrew Python recommended):
    brew install python
    pip install pygame pyserial


--------------------------------------------------
2️⃣ FIND YOUR ROBOT ARM SERIAL PORT
--------------------------------------------------

Plug in your robotic arm via USB.

WINDOWS:
    Open Command Prompt and run:
        mode

    Or:
        python -m serial.tools.list_ports

    Look for something like:
        COM3
        COM4

LINUX:
    Open terminal and run:
        ls /dev/tty*

    Usually:
        /dev/ttyUSB0
        /dev/ttyACM0

MACOS:
    Open terminal and run:
        ls /dev/tty.*

    Usually:
        /dev/tty.usbserial-XXXX
        /dev/tty.usbmodemXXXX


--------------------------------------------------
3️⃣ RUN THE SCRIPT
--------------------------------------------------

Edit the script and change:

    SERIAL_PORT = "COM3"

to your actual port.

Then run:

    python ps4_robot_arm_control.py


--------------------------------------------------
4️⃣ CONTROLLER TROUBLESHOOTING
--------------------------------------------------

This script prints controller inputs ONLY when they change.

Example output:

    BUTTON PRESSED: 1
    AXIS MOVED: 0 → -0.54

Use these values to remap controls easily inside the script.


--------------------------------------------------
5️⃣ CONTROLS (DEFAULT MAPPING)
--------------------------------------------------

Left Stick:
    X-axis → Move arm left/right
    Y-axis → Move arm forward/backward

Right Stick:
    Y-axis → Move arm up/down

R2:
    Close gripper

L2:
    Open gripper


--------------------------------------------------
Project by Dean Zylman
Z-Robotics
