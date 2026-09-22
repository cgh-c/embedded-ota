# OTA 升级包打包 + 签名 + 验证手册

> 作用:重新生成一个 upgrade.swu 升级包(新 rootfs + 签名),并验证它是好的。
> 适用场景:改了 rootfs 内容后,重新打包升级包。

---

## 一、需要什么(全部在本地,路径如下)

| 文件/工具 | 路径 | 作用 |
| --- | --- | --- |
| 新 rootfs 镜像 | `$SDK/output/images/rootfs.ext2` | 要升级的新系统(含内核+设备树) |
| RSA 私钥 | `swupdate/keys/priv.pem` | 签名用(**保密,不能泄露**) |
| RSA 公钥 | `swupdate/keys/public.pem` | 验签用(公开,板子上也有一份) |
| sw-description | `swupdate/sw-description` | 升级说明书(写哪个分区、校验值) |
| openssl | 系统自带 | 算哈希 + 签名 + 验签 |
| cpio | 系统自带 | 打包成 .swu |

```bash
SDK=/home/cgh/embedded/100ask_imx6ull-sdk
cd /home/cgh/embedded/swupdate
```

---

## 二、打包步骤(按顺序,命令可直接复制)

### 步骤 1:压缩新 rootfs

**作用**:把 rootfs.ext2(500M)用 gzip 压成 rootfs.ext4.gz(约 50M),减小升级包体积。

```bash
gzip -c $SDK/Buildroot_2020.02.x/output/images/rootfs.ext2 > rootfs.ext4.gz
```

- `gzip` = 压缩工具
- `-c` = 输出到标准输出(不删原文件)
- `> rootfs.ext4.gz` = 重定向到压缩文件

### 步骤 2:计算 sha256

**作用**:算出压缩文件的哈希值,写进 sw-description,升级时 SWUpdate 用它校验文件没传错/没损坏。

```bash
sha256sum rootfs.ext4.gz
```

输出一串 64 位十六进制(如 `ef81c5c2...`),**把这串填到 sw-description 里的 `sha256 = "..."` 字段**(slotA 和 slotB 两处都填)。

### 步骤 3:签名 sw-description

**作用**:用私钥对 sw-description 做 RSA 签名,生成 sw-description.sig。升级时板子用公钥验签,证明"这个说明书是持有私钥的人写的"。

```bash
openssl dgst -sha256 -sign keys/priv.pem sw-description > sw-description.sig
```

- `openssl dgst` = 计算摘要
- `-sha256` = 用 SHA-256 算法
- `-sign keys/priv.pem` = 用私钥签名
- `sw-description` = 要签名的文件
- `> sw-description.sig` = 签名结果存到这里

### 步骤 4:打包成 .swu

**作用**:把"说明书 + 签名 + 新系统"按顺序打成一个 cpio 归档,这就是升级包 update.swu。

```bash
printf "sw-description\nsw-description.sig\nrootfs.ext4.gz\n" | cpio -ov -H crc > update.swu
```

- `printf "a\nb\nc\n"` = 输出三行文件名(SWUpdate 要求**这个顺序不能错**)
- `|` = 管道,把文件名列表传给 cpio
- `cpio -ov` = 创建归档、详细输出
- `-H crc` = 用 crc 格式(带校验)
- `> update.swu` = 打包结果

### 步骤 5:本地验签(打包后必做)

**作用**:打包完先在自己电脑上验证签名有效,确认没问题再传板子。

```bash
openssl dgst -sha256 -verify keys/public.pem -signature sw-description.sig sw-description
```

- `-verify keys/public.pem` = 用公钥验签
- 输出 `Verified OK` = 签名有效 ✓

---

## 三、部署 + 升级验证

```bash
# 1. 传升级包到板子(IP 换成板子实际的)
scp update.swu root@192.168.1.20:/tmp/

# 2. 执行升级(当前 A 槽 → 升级 B 槽)
ssh root@192.168.1.20 "swupdate -i /tmp/update.swu -e stable,slotB -f /etc/swupdate/swupdate.cfg -k /etc/swupdate/public.pem"

# 3. 预期看到:
#    Software updated successfully
#    upgrade done: switch boot_slot a -> b, rebooting
```

**注意**:板子上的 `/etc/swupdate/public.pem` 必须和本地 `keys/public.pem` 是**同一个**,否则验签失败(报 `EVP_DigestVerifyFinal failed`)。如果不一致:

```bash
scp keys/public.pem root@192.168.1.20:/etc/swupdate/public.pem
```

---

## 四、关键注意点

1. **改了 rootfs 必须重算 sha256 并更新 sw-description**,否则升级时哈希对不上。
2. **cpio 打包顺序不能错**:`sw-description` → `sw-description.sig` → `rootfs.ext4.gz`。
3. **私钥 priv.pem 绝不能泄露/提交**,它已经写进 .gitignore。公钥 public.pem 可以提交。
4. **板子公钥 = 本地公钥**,不一致就 scp 覆盖。
5. 打包完**先在本地验签**(步骤 5),`Verified OK` 再传板子。
