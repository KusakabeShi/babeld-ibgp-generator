#!/bin/bash

resolveip()
{
  : ${1:?Usage: resolve name}
  (
    PATH=$PATH:/usr/bin
    lookupresult=$(getent ahostsv4 "$1")
    if [ $? -eq 0 ]; then
        resultaddr=$(echo $lookupresult | head -n 1 | awk '{print $1}')
        echo $resultaddr
        return 0
    fi
    lookupresult=$(getent ahostsv6 $1)
    if [ $? -eq 0 ]; then
        resultaddr=$(echo $lookupresult | head -n 1 | awk '{print $1}')
        echo "[$resultaddr]"
        return 0
    fi
    echo "0.0.0.0"
    return 127
  )
}
set -x
ip route add {{ self_ip.v4 }}/32 dev lo proto 114 table 114 scope link
ip route add {{ self_ip.v6 }}/128 dev lo proto 114 table 114 scope link

cp bird/igp_metric.zero.conf bird/igp_metric.conf

{% for up in ups -%}
{{ up }}
{% endfor %}
mkdir -p /var/run/babeld
rm /var/run/babeld/rw.sock || true
rm /var/run/babeld/ro.sock || true
babeld -D -I /var/run/babeld.pid -S /var/lib/babeld/state -c babeld.conf

