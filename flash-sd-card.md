# SD 卡烧录操作手册

> 适用:imx6ull OTA 项目,把编译出的 img 镜像烧录到 SD 卡。
> 镜像产物:Buildroot `output/images/100ask-imx6ull-pro-512d-systemv-v1.img`

---

## 一、前提准备

1. **SD 卡插读卡器,读卡器插到物理机**
2. **VMware 里连接 USB 读卡器给虚拟机**
   - 菜单:虚拟机(VM) → 可移动设备 → 找到读卡器(如 "Genesys Logic USB Storage") → 连接
3. **⚠️ 关键坑:USB 控制器必须是 3.0+**
   - 默认 VMware USB 控制器是 2.0,USB 3.0 读卡器会报
     "无法连接到理想的主机控制器"
   - 修复:关闭虚拟机 → 虚拟机设置 → USB 控制器 → USB 兼容性改为 **USB 3.1**
   - 改完开机,再连接读卡器即可

---

## 二、烧录步骤

### 1. 确认 SD 卡设备名(务必!别烧错盘)

```bash
lsblk -o NAME,SIZE,TYPE,MODEL
```

- 找 59.2G 的 `MassStorageClass` 磁盘(64G SD 卡)→ 例如 `/dev/sdb`
- **虚拟机系统盘是 `/dev/sda`(200G),绝不能碰!**

### 2. 卸载 SD 卡自动挂载的分区

Ubuntu 会自动挂载 SD 卡的 ext4 分区,先卸载:

```bash
sudo umount /dev/sdb1 /dev/sdb2 /dev/sdb3 2>/dev/null
```

### 3. 烧录

```bash
sudo dd if=<img路径> of=/dev/sdb bs=4M conv=fsync status=progress
```

> `of=/dev/sdb` 是整个设备(不带分区号!)。1.49G 大约 1~3 分钟。

### 4. 同步并完成

```bash
sync
```

### 5. 验证

```bash
lsblk /dev/sdb   # 应看到 3 个分区:sdb1=1G sdb2=1G sdb3=4G
```

---

## 三、注意事项

- **eMMC(板子上的 mmcblk1)绝对不能碰** —— 烧录只针对 SD 卡,虚拟机里只有 SD 卡(读卡器)和系统盘,烧录前用 lsblk 反复确认设备名。
- **`of=` 用整个设备**(`/dev/sdb`),不是分区(`/dev/sdb1`)。
- 新镜像烧录后 U-Boot 环境变量会重置(因为 dd 覆盖了整个卡),`boot_slot` 回到默认 `a`。

---


- 虚拟机系统盘:`/dev/sda`(200G,勿碰)
- SD 卡(读卡器):`/dev/sdb`(59.2G)+ 一个 0B 的空 LUN `/dev/sdc`(忽略)
- img 路径:`/home/cgh/embedded/100ask_imx6ull-sdk/Buildroot_2020.02.x/output/images/100ask-imx6ull-pro-512d-systemv-v1.img`
- 串口:`/dev/ttyACM0`(连开发板,115200)
