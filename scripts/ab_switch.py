import serial, time

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)

def drain(ser, label, wait=1.0):
    time.sleep(wait)
    data = ser.read(ser.in_waiting or 1)
    print(f"--- {label} ---")
    print(data.decode('utf-8', errors='replace'))
    return data

# 1. 重启开发板
print("=== 步骤1: 重启 ===")
ser.write(b'reboot\r\n')
time.sleep(4)

# 2. 持续发回车,中断 U-Boot autoboot(3秒窗口)
print("=== 步骤2: 中断 autoboot 进 U-Boot ===")
for i in range(10):
    ser.write(b'\r\n')
    time.sleep(0.4)

drain(ser, "U-Boot 状态", 2.0)

# 3. 执行切换
print("=== 步骤3: setenv boot_slot b ===")
ser.write(b'setenv boot_slot b\r\n')
drain(ser, "setenv 结果", 1.5)

ser.write(b'saveenv\r\n')
drain(ser, "saveenv 结果", 2.0)

ser.write(b'reset\r\n')
drain(ser, "reset", 1.0)

# 4. 等系统重启进 Linux,登录,查 cmdline
print("=== 步骤4: 等待重启进 Linux ===")
time.sleep(8)
ser.write(b'root\r\n')
time.sleep(2)
ser.write(b'\r\n')
time.sleep(2)
ser.write(b'cat /proc/cmdline\r\n')
drain(ser, "重启后的 cmdline", 3.0)

ser.close()
