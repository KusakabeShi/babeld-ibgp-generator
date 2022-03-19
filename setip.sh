ip link set {{ ifname }} up
{% if MTU > 0 -%}
ip link set mtu {{ MTU }} dev {{ ifname }}
{% endif %}
ip addr add {{ ipv4 }}/32 dev {{ ifname }}
ip addr add {{ ipv6 }}/128 dev {{ ifname }}
ip addr add {{ ipv6ll }}/64 dev {{ ifname }} scope link
