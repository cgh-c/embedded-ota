# OTA 升级演示流程

> 本文档逐步演示一次完整的 OTA 升级过程，每步含命令与预期输出。

---

## 一、项目介绍(开场词)

这是一个基于 **i.MX6ULL** 的嵌入式 Linux **OTA 远程升级系统**,核心用了三个东西:

- **SWUpdate** —— 工业级 OTA 升级框架,负责下载、验签、写盘、切槽
- **A/B 双分区** —— 系统存两份(A 槽 / B 槽),升级只写"没在用的那个槽",失败能回滚
- **RSA 签名** —— 升级包带签名,防篡改

接下来演示一次完整的升级:**把系统从 1.0.0 升级到 2.0.0**,全程通过网线远程完成,不插烧录线。

---

## 二、演示前准备(先确认状态)

录之前先在板子上跑这三条,确认是"干净的起点":

```bash
cat /proc/cmdline        # 预期含 root=/dev/mmcblk0p1  → A 槽
fw_printenv boot_slot    # 预期 boot_slot=a
cat /etc/sw-versions     # 预期 rootfs 1.0.0
```

再确认网络(升级要靠它传包):

```bash
ip addr show eth0        # 记下 IP,比如 192.168.1.20
```

---

## 三、演示步骤

### 第一幕:展示 A/B 分区 + 当前版本

**讲解词**:系统分了三个分区,rootfsA 和 rootfsB 是两份独立的系统,data 存用户数据。当前从 A 槽启动,版本 1.0.0。

**命令 1:展示三个分区**

```bash
ls -l /dev/mmcblk0p*
```

**预期输出**:
```
/dev/mmcblk0p1    ← A 槽(rootfsA)
/dev/mmcblk0p2    ← B 槽(rootfsB)
/dev/mmcblk0p3    ← data(用户数据)
```

**命令 2:展示当前从哪个分区启动**

```bash
cat /proc/cmdline
```

**预期输出**:含 `root=/dev/mmcblk0p1`

**命令 3:展示切槽开关**

```bash
fw_printenv boot_slot
```

**预期输出**:`boot_slot=a`

**命令 4:展示当前版本**

```bash
cat /etc/sw-versions
```

**预期输出**:`rootfs 1.0.0`

**这幕说明了什么**:SD 卡上确实有 A/B 两份系统,当前跑的是 A 槽的 1.0.0。

---

### 第二幕:执行升级

**讲解词**:升级包 52MB,里面带 RSA 签名。swupdate 会先验签确认包可信,然后写入**备用槽 B**,完全不动正在运行的 A 槽,写完自动切槽重启。

**命令 1:把升级包传到板子(电脑上操作,IP 换成实际)**

```bash
scp /home/cgh/embedded/swupdate/update.swu root@192.168.1.20:/tmp/
```

**预期输出**:传输进度条,100%。

**命令 2:执行升级(电脑上操作)**

```bash
ssh root@192.168.1.20 "swupdate -i /tmp/update.swu -e stable,slotB -f /etc/swupdate/swupdate.cfg -k /etc/swupdate/public.pem"
```

**预期输出**(关键镜头):
```
Software updated successfully
upgrade done: switch boot_slot a -> b, rebooting
```

然后板子**自动重启**。

**这幕说明了什么**:升级包验签通过后,写进 B 槽(不碰正在跑的 A 槽),写完切槽重启 —— 这就是 OTA 的核心闭环。

---

### 第三幕:验证升级结果

**讲解词**:重启后系统从 B 槽启动了,版本号从 1.0.0 变成了 2.0.0,说明升级真正生效。

**命令 1:版本号变了(核心镜头)**

```bash
cat /etc/sw-versions
```

**预期输出**:`rootfs 2.0.0` ← 从 1.0.0 变成了 2.0.0

**命令 2:启动分区也变了**

```bash
cat /proc/cmdline
```

**预期输出**:含 `root=/dev/mmcblk0p2` ← 从 B 槽启动

**命令 3:切槽开关也变了**

```bash
fw_printenv boot_slot
```

**预期输出**:`boot_slot=b`

**这幕说明了什么**:版本升级生效、启动槽从 A 切到 B,整个 OTA 升级闭环跑通。

---

## 四、整场演示说明了什么(结尾总结词)

1. **A/B 双分区成立**:系统有 A/B 两份,靠一个 `boot_slot` 变量切换,升级永远写"备用槽",不碰正在运行的系统。
2. **在线升级闭环跑通**:传包 → 验签 → 写备用槽 → 切槽 → 重启,全自动完成,无需插线烧录。
3. **升级有安全底线**:RSA 签名 + sha256 校验,被篡改的包装不进去。
4. **具备回滚能力**:升级写的是备用槽,新系统有问题时,切回旧槽就能恢复。

---

## 附:回退演示(可选加分项)

如果想让视频更完整,可以在升级前加一段"回退演示":

```bash
# 假设当前在 B 槽 2.0.0,演示切回 A 槽 1.0.0
fw_setenv boot_slot a
/sbin/reboot

# 重启后验证
cat /etc/sw-versions     # rootfs 1.0.0(回退了)
cat /proc/cmdline        # root=/dev/mmcblk0p1(A 槽)
```

**这说明了什么**:A/B 双分区的核心价值 —— 新系统出问题,切回旧槽就能救回来,设备不砖。
