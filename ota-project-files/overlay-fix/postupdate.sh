#!/bin/sh
# SWUpdate 升级成功后:切换 boot_slot 到刚升级的备用槽,然后重启
CUR=$(/usr/sbin/fw_printenv -n boot_slot 2>/dev/null)

if [ "$CUR" = "a" ]; then
    /usr/sbin/fw_setenv boot_slot b
    echo "upgrade done: switch boot_slot a -> b, rebooting"
elif [ "$CUR" = "b" ]; then
    /usr/sbin/fw_setenv boot_slot a
    echo "upgrade done: switch boot_slot b -> a, rebooting"
else
    echo "ERROR: cannot read boot_slot (got '$CUR')"
    exit 1
fi

sync
/sbin/reboot
