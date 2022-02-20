ip link add dev {{ ifname }} type wireguard
wg setconf {{ ifname }} {{ confpath }}.conf