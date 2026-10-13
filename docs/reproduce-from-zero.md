# 从 0 复现完整流程

> 从"拿到一块板子"到"跑通 OTA 升级"的完整步骤。每步:命令 + 预期结果 + 意义。
> 假设在 Ubuntu 虚拟机上操作( SDK 的编译环境)。

---

## 0. 硬件准备

| 硬件 | 说明 |
|---|---|
| 开发板 |  100ask imx6ull pro(512MB DDR) |
| SD 卡 | ≥8G(装得下 1G+1G+4G 三个分区 + U-Boot) |
| 串口线 | 115200,用于看日志、进 U-Boot |
| 网线 | 升级时传包用 |

---

## 1. 下载 SDK(内核 + Buildroot + 工具链)

**是什么**:用 repo 工具,一次性把打包好的整套 SDK 拉下来。

**为什么**:SDK 里已经包含 Linux 4.9.88 内核源码、Buildroot 2020.02.x、交叉工具链、U-Boot 配置,且板子每个外设都调通了。从它开始,省去自己从 NXP 官方 SDK 从零移植 BSP 的几周时间。

```bash
# 1. 下载 repo 工具(Google 多仓库管理工具)
git clone https://e.coding.net/codebug8/repo.git

# 2. 创建 SDK 目录
mkdir -p 100ask_imx6ull-sdk && cd 100ask_imx6ull-sdk

# 3. 初始化 repo(指定 imx6ull pro 的 Linux 4.9.88 版本)
../repo/repo init -u https://gitee.com/weidongshan/manifests.git \
    -b linux-sdk \
    -m imx6ull/100ask_imx6ull_linux4.9.88_release.xml \
    --no-repo-verify

# 4. 同步下载(4 线程并行)
../repo/repo sync -j4
```

**参数说明**:
- `-u https://gitee.com/weidongshan/manifests.git`:manifest(清单)仓库地址
- `-b linux-sdk`:分支
- `-m imx6ull/100ask_imx6ull_linux4.9.88_release.xml`:指定 imx6ull pro 的 Linux 4.9.88 版本清单
- `--no-repo-verify`:跳过 repo 工具完整性验证

**预期结果**:目录下出现三个东西:
```
Linux-4.9.88        ← 内核源码
Buildroot_2020.02.x ← 构建系统(含 genimage、工具链编译)
ToolChain           ← 预编译交叉工具链
```

**意义**:编译原料到齐。内核、Buildroot、工具链都是 repo 一次拉下来的,不用分开下载。

---

## 2. 配置 Buildroot

**是什么**:告诉 Buildroot"编哪块板子、什么配置"。

**为什么**:Buildroot 支持无数板子,靠 defconfig 决定内核配置、rootfs 内容、U-Boot 版本。我们选 pro 版 + 512M DDR + systemV + core。

```bash
cd 100ask_imx6ull-sdk/Buildroot_2020.02.x
make 100ask_imx6ull_pro_ddr512m_systemV_core_defconfig
```

**预期结果**:生成 `.config` 文件。

**意义**:配置就位,`make` 时知道要编什么。

---

## 3. 集成项目改造(A/B 分区 + 切槽 + 双网口 + 升级环境)

这是本项目对 SDK 做的**四处改造**,把项目提供的文件覆盖到对应位置。

### 3.1 改 A/B 分区(genimage.cfg)

**改的文件**:`Buildroot_2020.02.x/board/100ask/nxp-imx6ull/genimage.cfg`(文本配置,定义 img 里的分区)

**改前(原始,非 A/B 的三分区)**:

```
u-boot       offset=1024, 2M   (分区表外)
rootfs-1     100M, bootable    (无 image,预留)
rootfs-2     800M, bootable    (rootfs.ext4,真正的系统)
userdate     50M, FAT(0xC)     (FAT 分区)
```

**改后(A/B + data)**:

```
u-boot       offset=1024, 2M   (不变)
rootfsA      1G, bootable      (rootfs.ext4,A 槽)
rootfsB      1G                (rootfs.ext4,B 槽)
data         4G                (ext,数据区)
```

**操作**:直接编辑这个文件,把分区定义改了(或用项目提供的覆盖),然后重新 `make`:

```bash
cp ota-project-files/genimage.cfg $BR/board/100ask/nxp-imx6ull/genimage.cfg
```

**核心改动**:把原来"预留 + 系统 + FAT"三个分区,改造成两个**对等的 rootfs 分区(A/B 槽)+ 一个数据区**。两个 rootfs 都指向同一个 rootfs.ext4 镜像,所以一开始 A、B 装的是同一份系统。

**意义**:SD 卡上有了两份可切换的 rootfs,升级才有地方写。

### 3.2 改 U-Boot 切槽(mx6ullevk.h)

让 U-Boot 读 `boot_slot` 环境变量决定启动哪个分区。U-Boot 源码是编译时才下载的,所以先触发下载再覆盖:

```bash
# 先让 Buildroot 下载 U-Boot 源码(会生成 output/build/uboot-* 目录)
cd $BR && make uboot-dirclean 2>/dev/null; make uboot-source 2>/dev/null

# 找到 U-Boot 源码目录(hash 目录名每次可能不同)
UB=$(ls -d $BR/output/build/uboot-* | grep -v tools | head -1)

# 用项目提供的 mx6ullevk.h 覆盖(含 boot_slot 切槽逻辑)
cp ota-project-files/mx6ullevk.h $UB/include/configs/mx6ullevk.h
```

**意义**:打通"改一个变量 = 换启动分区",这是 A/B 机制的控制核心。

### 3.3 改内核(双网口修复 + 设备树)

修复 fec 驱动只复位一个 PHY 的问题,并更新设备树:

```bash
SDK=100ask_imx6ull-sdk

# 内核驱动:遍历多个 phy-reset-gpios(修复 eth1 网口不通)
cp ota-project-files/eth1-fix/fec_main.c \
   $SDK/Linux-4.9.88/drivers/net/ethernet/freescale/fec_main.c

# 设备树:fec2 双复位 GPIO
cp ota-project-files/eth1-fix/100ask_imx6ull-14x14.dts \
   $SDK/Linux-4.9.88/arch/arm/boot/dts/100ask_imx6ull-14x14.dts
```

**意义**:这是"改内核源码 + 改设备树"的实战,修复必须固化进 img。

### 3.4 加 rootfs 覆盖层(SWUpdate 配置 + 网络 + sshd)

把升级环境预置进 rootfs:

```bash
BR=100ask_imx6ull-sdk/Buildroot_2020.02.x

# 覆盖到 imx6ull 的 systemV 覆盖层目录
cp -r ota-project-files/overlay/*   $BR/board/100ask/nxp-imx6ull/rootfs-overlay/systemV/
cp -r ota-project-files/overlay-fix/* $BR/board/100ask/nxp-imx6ull/rootfs-overlay/systemV/
```

内容包括:SWUpdate 配置、开机自动联网、sshd 自启、`/sbin/reboot` 绝对路径、公钥固化等。

**意义**:升级环境和安全公钥都固化进镜像。

**安装 SWUpdate**(靠 Buildroot 自动编译,不手动装):

1. 在 Buildroot 配置里开启 SWUpdate 包和 openssl(SWUpdate 验签依赖):

```bash
cd 100ask_imx6ull-sdk/Buildroot_2020.02.x
make menuconfig        # 图形界面勾选,或直接编辑 defconfig 加下面两行:
#   BR2_PACKAGE_SWUPDATE=y
#   BR2_PACKAGE_OPENSSL=y
```

2. 之后 `make` 时,Buildroot 自动下载 SWUpdate 2019.11 源码、交叉编译、装进 rootfs 的 `/usr/bin/swupdate`。

---

## 4. 编译

**是什么**:一条 `make`,Buildroot 自动完成整个编译链。

**为什么**:Buildroot 的编排能力——按依赖顺序:先编交叉工具链,再编 U-Boot、内核、rootfs,最后 genimage 打包。

```bash
cd 100ask_imx6ull-sdk/Buildroot_2020.02.x
make
```

**耗时**(实测 build-time.log):所有包纯编译合计约 **30 分钟**;含下载源码/配置/安装,单次完整编译约 **1 小时**。其中工具链 gcc 约 3 分钟、内核约 2.6 分钟、U-Boot 约 0.9 分钟。

**预期结果**:`output/images/` 下生成:
```
100ask-imx6ull-pro-512d-systemv-v1.img  ← 完整 SD 卡镜像(1.49G)
zImage                                 ← 内核
100ask_imx6ull-14x14.dtb               ← 设备树
u-boot-dtb.imx                         ← U-Boot
```

**意义**:所有改造固化进一个 .img,可以烧录了。

---

## 5. 制作升级包(签名)

**是什么**:把新 rootfs 打包成带 RSA 签名的 update.swu。

**为什么**:升级包要有签名,板子才能验签、防篡改。

```bash
# 1. 生成 RSA 密钥对(只需一次)
openssl genrsa -out swupdate/keys/priv.pem 2048
openssl rsa -in swupdate/keys/priv.pem -pubout -out swupdate/keys/public.pem

# 2. 压缩 rootfs
gzip -c output/images/rootfs.ext4 > swupdate/rootfs.ext4.gz

# 3. 计算 rootfs.ext4.gz 的 sha256,写进 sw-description(slotA/slotB 两处)
SHA=$(sha256sum swupdate/rootfs.ext4.gz | awk '{print $1}')
sed -i "s/sha256 = \".*\"/sha256 = \"$SHA\"/g" swupdate/sw-description

# 4. 签名 sw-description
openssl dgst -sha256 -sign swupdate/keys/priv.pem \
    -out swupdate/sw-description.sig swupdate/sw-description

# 5. 打包成 update.swu(cpio 格式,顺序:sw-description → 签名 → rootfs)
cd swupdate
printf "sw-description\nsw-description.sig\nrootfs.ext4.gz\n" | cpio -ov -H crc > update.swu
```

**⚠️ 关键**:cpio 打包命令**严禁加 `2>&1`**(会把错误信息混进归档,导致 magic not found)。

**意义**:得到带签名的升级包 update.swu。

---

## 6. 烧录镜像

```bash
# 确认 SD 卡设备名(通常 /dev/sdb,系统盘 /dev/sda 绝不能碰!)
lsblk -o NAME,SIZE,TYPE,MODEL

# 烧录
sudo dd if=output/images/100ask-imx6ull-pro-512d-systemv-v1.img \
        of=/dev/sdb bs=4M conv=fsync status=progress
sync
```

**预期结果**:`lsblk /dev/sdb` 看到 sdb1=1G、sdb2=1G、sdb3=4G。

---

## 7. 验证 A/B 切槽

SD 卡插回板子上电,串口登录:

```bash
cat /proc/cmdline        # root=/dev/mmcblk0p1(A 槽)
fw_printenv boot_slot    # boot_slot=a
cat /etc/sw-versions     # rootfs 1.0.0
```

**意义**:确认 A/B 分区和切槽机制正常。

---

## 8. 在线升级

```bash
# 电脑上:传升级包 + 升级(当前 A 槽 → 写 B 槽)
scp swupdate/update.swu root@<板子IP>:/tmp/
ssh root@<板子IP> "swupdate -i /tmp/update.swu -e stable,slotB \
    -f /etc/swupdate/swupdate.cfg -k /etc/swupdate/public.pem"
```

**预期结果**:`Software updated successfully` + 自动重启。

重启后验证:
```bash
cat /etc/sw-versions     # rootfs 2.0.0(升级生效)
cat /proc/cmdline        # root=/dev/mmcblk0p2(B 槽)
```

**意义**:OTA 升级闭环跑通。
