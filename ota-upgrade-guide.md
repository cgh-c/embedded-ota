# OTA 升级操作手册

> 适用:imx6ull OTA 项目,从"生成升级包"到"部署验证"的完整流程。
> 前提:板子已烧录含 swupdate 的镜像,eth0 网口已接路由器。

---

## 一、整体流程概览

```
① 生成升级包            ② 部署升级             ③ 自动切槽重启
rootfs.ext2 压缩        scp .swu 到板子          postupdate 切 boot_slot
  ↓ gzip                   ↓ swupdate 写备用槽      ↓ reboot
rootfs.ext4.gz          升级 B 槽(写 p2)        从 B 槽启动
  ↓ sha256 + 签名
update.swu
```

**核心概念**:永远升级"备用槽",升级成功后切槽重启。当前在 A 槽就升 B 槽,反之亦然。

---

## 二、生成升级包(在虚拟机上)

```bash
cd /home/cgh/embedded/swupdate

# 1. 压缩 rootfs(如果重新编译了系统,rootfs.ext2 会更新)
gzip -c /home/cgh/embedded/100ask_imx6ull-sdk/Buildroot_2020.02.x/output/images/rootfs.ext2 > rootfs.ext4.gz

# 2. 计算 sha256
sha256sum rootfs.ext4.gz
# 输出如:303c8ed5...  rootfs.ext4.gz  ← 把这串填到 sw-description 的 sha256 字段

# 3. 签名 sw-description(RSA 私钥)
openssl dgst -sha256 -sign keys/priv.pem sw-description > sw-description.sig

# 4. 打包成 .swu(顺序不能错:description → sig → 镜像)
printf "sw-description\nsw-description.sig\nrootfs.ext4.gz\n" | cpio -ov -H crc > update.swu
```

> ⚠️ 改了 rootfs 后必须重新算 sha256 并更新 sw-description,否则验签时哈希对不上。

---

## 三、部署升级

### 0. 确认板子网络(每次重启后可能没自动 DHCP)

```bash
# 串口登录后手动拿 IP(如果 eth0 没 IP)
udhcpc -i eth0 -n
# 记下拿到的 IP,通常是 192.168.1.15
```

### 1. 确认当前在哪个槽

```bash
ssh root@192.168.1.15 "/usr/sbin/fw_printenv boot_slot"
# 输出 boot_slot=a 或 boot_slot=b
```

### 2. 传升级包 + 升级

**当前在 A 槽 → 升级 B 槽**:
```bash
scp update.swu root@192.168.1.15:/tmp/
ssh root@192.168.1.15 "swupdate -i /tmp/update.swu -e stable,slotB -f /etc/swupdate/swupdate.cfg -k /etc/swupdate/public.pem"
```

**当前在 B 槽 → 升级 A 槽**(把 slotB 换成 slotA):
```bash
ssh root@192.168.1.15 "swupdate -i /tmp/update.swu -e stable,slotA -f /etc/swupdate/swupdate.cfg -k /etc/swupdate/public.pem"
```

关键参数:
| 参数 | 含义 |
| --- | --- |
| `-i /tmp/update.swu` | 升级包路径 |
| `-e stable,slotB` | 选 B 槽(写 p2);slotA = 写 p1 |
| `-f ...swupdate.cfg` | 配置(含 postupdate 切槽脚本) |
| `-k ...public.pem` | 验签公钥 |

### 3. 升级成功后自动重启

看到 `Software updated successfully` + `switch boot_slot a -> b, rebooting` 后,板子自动切槽重启。

---

## 四、验证升级结果

等 40 秒(板子重启),串口登录验证:

```bash
cat /proc/cmdline
# 应该是 root=/dev/mmcblk0p2(升级到了 B 槽)

/usr/sbin/fw_printenv boot_slot
# 应该是 boot_slot=b
```

---

## 五、防篡改验证(可选)

```bash
# 篡改升级包一个字节
cp update.swu /tmp/update-bad.swu
printf '\x00' | dd of=/tmp/update-bad.swu bs=1 seek=1000000 conv=notrunc
scp /tmp/update-bad.swu root@192.168.1.15:/tmp/

# 升级应该被拒绝(校验失败,不会安装)
ssh root@192.168.1.15 "swupdate -i /tmp/update-bad.swu -e stable,slotB -k /etc/swupdate/public.pem 2>&1 | tail -5"
# 看到 Checksum/verification failed 即验证通过
```

---

## 六、常见坑速查

| 坑 | 现象 | 解法 |
| --- | --- | --- |
| sw-description 语法 | `Found nothing to install` | 用 `software → stable → slotA/slotB → images` 结构 |
| 忘了加 sha256 | 验签失败 | 每个镜像都要有 sha256 字段 |
| 改 rootfs 没重算 sha256 | 哈希对不上 | 重新 sha256sum 并更新 sw-description |
| 切槽后 swupdate 变旧 | `-k` 报 invalid option | 每槽独立 rootfs,新 swupdate 要传两次(或编译进镜像) |
| 重启后没网 | ssh 连不上 | 串口登录后手动 `udhcpc -i eth0 -n` |

---

## 七、关键文件位置

| 文件 | 位置 |
| --- | --- |
| 升级包 | `/home/cgh/embedded/swupdate/update.swu` |
| 描述文件 | `/home/cgh/embedded/swupdate/sw-description` |
| 私钥/公钥 | `/home/cgh/embedded/swupdate/keys/` |
| rootfs 镜像 | `Buildroot_2020.02.x/output/images/rootfs.ext2` |
| 板子 swupdate | `/usr/bin/swupdate`(板子上) |
| 板子公钥 | `/etc/swupdate/public.pem`(板子上) |
| 板子切槽脚本 | `/etc/swupdate/postupdate.sh`(板子上) |
