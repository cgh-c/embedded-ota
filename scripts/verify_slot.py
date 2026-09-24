import serial, time

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
time.sleep(0.5)
ser.reset_input_buffer()

def run(cmd, wait=2.5):
    ser.write((cmd + '\r\n').encode())
    time.sleep(wait)
    data = ser.read(ser.in_waiting or 1)
    return data.decode('utf-8', errors='replace')

# 登录
run('root', 2)
run('', 2)

print("=== 启动槽(cmdline) ===")
print(run('cat /proc/cmdline', 2))

print("=== boot_slot ===")
print(run('/usr/sbin/fw_printenv boot_slot', 2))

print("=== 升级版本标记 ===")
print(run('cat /etc/sw-versions 2>/dev/null; ls /update-ok 2>/dev/null && echo "有update-ok标记"', 2))

ser.close()
