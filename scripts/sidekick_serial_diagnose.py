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
                print(f"<<< {line}")import serial
import time


with serial.Serial("/dev/ttyUSB0", 115200, timeout=0.4) as ser:
    ser.dtr = False
    ser.rts = False
    time.sleep(0.3)
    ser.reset_input_buffer()

    for command in ("GETVERSION", "GETWIFI", "GETSERVER"):
        print(f">>> {command}")
        ser.write((command + "\n").encode())
        ser.flush()
        deadline = time.time() + 2
        while time.time() < deadline:
            line = ser.readline().decode(errors="replace").strip()
            if line:
                print(f"<<< {line}")

    print(">>> waiting for poll diagnostics")
    deadline = time.time() + 17
    while time.time() < deadline:
        line = ser.readline().decode(errors="replace").strip()
        if line:
            print(f"<<< {line}")