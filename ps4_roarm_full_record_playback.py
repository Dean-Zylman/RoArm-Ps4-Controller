import pygame
import serial
import json
import time
import os
from datetime import datetime

"""
Full-episode recorder for RoArm-M2-S using a PS4 controller.

Behavior:
- Square: start recording (captures every frame)
- Triangle: stop recording and save to JSON
- Circle: playback last recorded episode (timing preserved)
- Cross: clear current episode

Recording captures every pose the script sends, with precise timing, so
playback mirrors the original motion.
"""

# ==========================
# USER CONFIG
# ==========================
SERIAL_PORT = "/dev/tty.usbserial-10"
BAUDRATE = 115200

UPDATE_HZ = 30        # control loop Hz
POS_STEP = 6.0        # XY mm per tick at full stick
Z_STEP = 5.0          # Z mm per tick at full stick

# Gripper angles (radians)
GRIPPER_OPEN = 3.14
GRIPPER_CLOSED = 1.08
GRIPPER_STEP = 0.04

# Safe start
x, y, z = 220, 0, 200
t = GRIPPER_OPEN

# Workspace limits (mm)
X_MIN, X_MAX = 50, 400
Y_MIN, Y_MAX = -250, 250
Z_MIN, Z_MAX = -150, 300

# Folder to store all recordings
EPISODES_DIR = "episodes"

# ==========================
# SERIAL SETUP
# ==========================
ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.01)
ser.setRTS(False)
ser.setDTR(False)
time.sleep(2)


def send(cmd: dict) -> None:
    msg = json.dumps(cmd)
    ser.write((msg + "\n").encode("utf-8"))


def read_serial() -> None:
    try:
        line = ser.readline().decode("utf-8").strip()
        if line:
            pass
    except Exception:
        pass


# ==========================
# INIT ROBOT
# ==========================
send({"T": 210, "cmd": 1})  # torque ON
time.sleep(0.3)

# ==========================
# PYGAME
# ==========================
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise RuntimeError("No PS4 controller detected")

js = pygame.joystick.Joystick(0)
js.init()

print("Controller:", js.get_name())
clock = pygame.time.Clock()


def dz(v, d=0.12):
    return 0.0 if abs(v) < d else v


# ==========================
# RECORD / PLAYBACK STATE
# ==========================
recording = False
record_start_ts = 0.0
last_record_ts = 0.0
episode = []  # list of {dt, pose}

prev_buttons = {}

# ==========================
# SIMPLE UI (Pygame overlay)
# ==========================
ui_width = 420
ui_height = 320
screen = pygame.display.set_mode((ui_width, ui_height))
pygame.display.set_caption("RoArm Recorder")
font = pygame.font.SysFont("Arial", 16)

name_text = ""
loop_text = "1"
status_text = "Idle"
typing_name = False
typing_loop = False

episode_files = []
selected_index = 0
stop_requested = False
playback_active = False
playback_loop_count = 1
playback_loop_index = 0
playback_frame_index = 0
playback_next_ts = 0.0


def sanitize_name(name: str) -> str:
    cleaned = []
    for ch in name.strip():
        if ch.isalnum() or ch in ("-", "_"):
            cleaned.append(ch)
        elif ch.isspace():
            cleaned.append("_")
    return "".join(cleaned)


def refresh_episode_files() -> None:
    global episode_files, selected_index
    os.makedirs(EPISODES_DIR, exist_ok=True)
    files = [f for f in os.listdir(EPISODES_DIR) if f.endswith(".json")]
    files.sort()
    episode_files = files
    if not episode_files:
        selected_index = 0
    else:
        selected_index = max(0, min(selected_index, len(episode_files) - 1))


def selected_episode_path() -> str:
    if not episode_files:
        return ""
    return os.path.join(EPISODES_DIR, episode_files[selected_index])


def button_pressed(idx: int) -> bool:
    current = bool(js.get_button(idx))
    prev = prev_buttons.get(idx, False)
    prev_buttons[idx] = current
    return current and not prev


def current_pose() -> dict:
    return {
        "T": 1041,
        "x": round(x, 1),
        "y": round(y, 1),
        "z": round(z, 1),
        "t": round(t, 3),
    }


def start_recording() -> None:
    global recording, record_start_ts, last_record_ts, episode
    recording = True
    episode = []
    record_start_ts = time.monotonic()
    last_record_ts = record_start_ts
    print("Recording started")


def stop_and_save() -> str:
    global recording, status_text
    if not recording:
        print("Not recording")
        status_text = "Not recording"
        return ""
    recording = False
    if not episode:
        print("Recording empty; nothing to save")
        status_text = "Empty recording"
        return ""
    os.makedirs(EPISODES_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_name(name_text)
    if safe_name:
        filename = os.path.join(EPISODES_DIR, f"{safe_name}_{ts}.json")
    else:
        filename = os.path.join(EPISODES_DIR, f"episode_full_{ts}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(episode, f, indent=2)
    print(f"Saved episode to {filename}")
    status_text = f"Saved: {os.path.basename(filename)}"
    refresh_episode_files()
    return filename


def record_frame() -> None:
    global last_record_ts
    now = time.monotonic()
    dt = now - last_record_ts
    last_record_ts = now
    episode.append({
        "dt": round(dt, 4),
        "pose": current_pose(),
    })


def playback_episode() -> None:
    global stop_requested, status_text, playback_active
    global playback_loop_count, playback_loop_index, playback_frame_index, playback_next_ts
    if not episode:
        print("Nothing to play: episode is empty")
        status_text = "Nothing to play"
        return
    try:
        loops = int(loop_text.strip() or "1")
    except ValueError:
        loops = 1
    loops = max(1, loops)
    print(f"Playing back {len(episode)} frames x{loops}...")
    status_text = f"Playing x{loops}"
    stop_requested = False
    playback_active = True
    playback_loop_count = loops
    playback_loop_index = 0
    playback_frame_index = 0
    playback_next_ts = time.monotonic()


def stop_arm() -> None:
    """Abort playback and release torque."""
    global stop_requested, status_text, playback_active
    stop_requested = True
    playback_active = False
    send({"T": 210, "cmd": 0})
    status_text = "Torque OFF"


def start_recording_ui() -> None:
    global status_text
    start_recording()
    status_text = "Recording..."


def stop_and_save_ui() -> None:
    stop_and_save()


def playback_ui() -> None:
    playback_episode()


def load_selected_episode() -> None:
    global episode, status_text
    path = selected_episode_path()
    if not path:
        status_text = "No files to load"
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            episode = json.load(f)
        print(f"Loaded episode: {path}")
        status_text = f"Loaded: {os.path.basename(path)}"
    except Exception as e:
        print(f"Failed to load episode: {e}")
        status_text = "Load failed"


def draw_ui() -> None:
    screen.fill((24, 24, 28))
    # Name field
    name_label = font.render("Recording name:", True, (220, 220, 220))
    screen.blit(name_label, (12, 12))
    name_box = pygame.Rect(12, 34, 396, 28)
    pygame.draw.rect(screen, (40, 40, 48), name_box, border_radius=4)
    pygame.draw.rect(screen, (90, 90, 110), name_box, 2, border_radius=4)
    name_value = name_text if name_text else "(optional)"
    name_color = (230, 230, 230) if name_text else (140, 140, 160)
    name_render = font.render(name_value, True, name_color)
    screen.blit(name_render, (18, 40))
    if typing_name:
        caret_x = 18 + name_render.get_width() + 2
        pygame.draw.line(screen, (230, 230, 230), (caret_x, 40), (caret_x, 56), 1)

    # Loop count
    loop_label = font.render("Loop count:", True, (220, 220, 220))
    screen.blit(loop_label, (12, 66))
    loop_box = pygame.Rect(100, 62, 60, 24)
    pygame.draw.rect(screen, (40, 40, 48), loop_box, border_radius=4)
    pygame.draw.rect(screen, (90, 90, 110), loop_box, 2, border_radius=4)
    loop_value = loop_text if loop_text else "1"
    loop_color = (230, 230, 230) if loop_text else (140, 140, 160)
    loop_render = font.render(loop_value, True, loop_color)
    screen.blit(loop_render, (106, 66))
    if typing_loop:
        caret_x = 106 + loop_render.get_width() + 2
        pygame.draw.line(screen, (230, 230, 230), (caret_x, 66), (caret_x, 80), 1)

    # Buttons
    buttons = [
        ("Start Recording", (12, 94, 190, 32)),
        ("Stop + Save", (218, 94, 190, 32)),
        ("Play Recording", (12, 136, 190, 32)),
        ("Load Selected", (218, 136, 190, 32)),
        ("Prev File", (12, 178, 190, 32)),
        ("Next File", (218, 178, 190, 32)),
    ]
    for text, rect in buttons:
        r = pygame.Rect(rect)
        pygame.draw.rect(screen, (60, 60, 78), r, border_radius=6)
        pygame.draw.rect(screen, (120, 120, 150), r, 2, border_radius=6)
        label = font.render(text, True, (240, 240, 240))
        screen.blit(label, (r.x + 10, r.y + 7))

    # Selected file
    refresh_episode_files()
    file_label = "None" if not episode_files else episode_files[selected_index]
    file_render = font.render(f"Selected: {file_label}", True, (200, 200, 200))
    screen.blit(file_render, (12, 260))

    # Status
    status_render = font.render(f"Status: {status_text}", True, (200, 200, 200))
    screen.blit(status_render, (12, 282))

    pygame.display.flip()

# ==========================
# MAIN LOOP
# ==========================
while True:
    pygame.event.pump()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            raise SystemExit
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            # Name field focus
            if pygame.Rect(12, 34, 396, 28).collidepoint(mx, my):
                typing_name = True
                typing_loop = False
            elif pygame.Rect(100, 62, 60, 24).collidepoint(mx, my):
                typing_loop = True
                typing_name = False
            else:
                typing_name = False
                typing_loop = False
            # Button hitboxes
            if pygame.Rect(12, 94, 190, 32).collidepoint(mx, my):
                start_recording_ui()
            elif pygame.Rect(218, 94, 190, 32).collidepoint(mx, my):
                stop_and_save_ui()
            elif pygame.Rect(12, 136, 190, 32).collidepoint(mx, my):
                playback_ui()
                if episode:
                    last = episode[-1]["pose"]
                    x, y, z, t = last["x"], last["y"], last["z"], last["t"]
                continue
            elif pygame.Rect(218, 136, 190, 32).collidepoint(mx, my):
                load_selected_episode()
            elif pygame.Rect(12, 178, 190, 32).collidepoint(mx, my):
                refresh_episode_files()
                if episode_files:
                    selected_index = max(0, selected_index - 1)
            elif pygame.Rect(218, 178, 190, 32).collidepoint(mx, my):
                refresh_episode_files()
                if episode_files:
                    selected_index = min(len(episode_files) - 1, selected_index + 1)
        if event.type == pygame.KEYDOWN and (typing_name or typing_loop):
            if event.key == pygame.K_RETURN:
                typing_name = False
                typing_loop = False
            elif event.key == pygame.K_BACKSPACE:
                if typing_name:
                    name_text = name_text[:-1]
                elif typing_loop:
                    loop_text = loop_text[:-1]
            else:
                if event.unicode and event.unicode.isprintable():
                    if typing_name:
                        name_text += event.unicode
                    elif typing_loop and event.unicode.isdigit():
                        loop_text += event.unicode

    # AXES (macOS mapping)
    lx = dz(js.get_axis(0))        # left stick X
    ly = dz(-js.get_axis(1))       # left stick Y
    rx = dz(js.get_axis(2))        # right stick X → GRIPPER
    ry = dz(-js.get_axis(3))       # right stick Y → Z

    # ==========================
    # POSITION UPDATE
    # ==========================
    x += ly * POS_STEP
    y -= lx * POS_STEP
    z += ry * Z_STEP

    x = max(X_MIN, min(X_MAX, x))
    y = max(Y_MIN, min(Y_MAX, y))
    z = max(Z_MIN, min(Z_MAX, z))

    # ==========================
    # GRIPPER CONTROL (RIGHT STICK X)
    # ==========================
    if rx != 0:
        t -= rx * GRIPPER_STEP

    t = max(GRIPPER_CLOSED, min(GRIPPER_OPEN, t))

    # ==========================
    # BUTTONS
    # ==========================
    if button_pressed(2):  # Square → start recording
        start_recording_ui()

    if button_pressed(3):  # Triangle → stop + save
        stop_and_save_ui()

    if button_pressed(1):  # Circle → stop arm / torque off
        stop_arm()
        continue

    if button_pressed(0):  # Cross → clear
        episode.clear()
        print("Episode cleared")

    # ==========================
    # PLAYBACK (non-blocking)
    # ==========================
    if playback_active:
        now = time.monotonic()
        if now >= playback_next_ts:
            frame = episode[playback_frame_index]
            send(frame["pose"])
            read_serial()
            playback_next_ts = now + frame["dt"]
            playback_frame_index += 1
            if playback_frame_index >= len(episode):
                playback_frame_index = 0
                playback_loop_index += 1
                if playback_loop_index >= playback_loop_count:
                    playback_active = False
                    status_text = "Idle"
        draw_ui()
        clock.tick(UPDATE_HZ)
        continue

    # ==========================
    # SEND COMMAND (live control)
    # ==========================
    send(current_pose())

    # Record every frame while recording
    if recording:
        record_frame()

    read_serial()
    draw_ui()
    clock.tick(UPDATE_HZ)
