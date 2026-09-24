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
out = run('', 2)
if 'incorrect' in out or 'login' in out.lower():
    print("登录可能失败,输出:")
    print(out)

# 改 fw_env.config 指向 SD 卡
run('echo "/dev/mmcblk0  0xe0000 0x2000" > /etc/fw_env.config', 2)
print("=== fw_env.config ===")
print(run('cat /etc/fw_env.config', 2))

print("=== boot_slot ===")
print(run('/usr/sbin/fw_printenv boot_slot', 3))

print("=== 关键环境变量 ===")
print(run('/usr/sbin/fw_printenv | grep -E "boot_slot|mmcpart|mmcroot|mmcdev"', 3))

ser.close()
