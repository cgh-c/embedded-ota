#!/bin/sh
# SWUpdate 升级成功后的回调:切换 boot_slot 到刚升级的备用槽
# 前提:启动脚本总是升级"非当前"槽(标准 A/B 做法)
CUR=$(/usr/sbin/fw_printenv -n boot_slot 2>/dev/null)

if [ "$CUR" = "a" ]; then
    /usr/sbin/fw_setenv boot_slot b
    echo "upgrade done: switch boot_slot a -> b"
elif [ "$CUR" = "b" ]; then
    /usr/sbin/fw_setenv boot_slot a
    echo "upgrade done: switch boot_slot b -> a"
else
    echo "ERROR: cannot read boot_slot (got '$CUR')"
    exit 1
fi

sync
