import serial
import time

with serial.Serial("/dev/ttyACM0", 115200, timeout=0.5) as ser:
    time.sleep(0.5)
    ser.reset_input_buffer()
    for command in ("GETVERSION", "GETWIFI", "GETSERVER"):
        print(f">>> {command}")
        ser.write((command + "\n").encode())
        ser.flush()
        deadline = time.time() + 3
        while time.time() < deadline:
            line = ser.readline().decode(errors="replace").strip()
            if line:
                print(f"<<< {line}")
