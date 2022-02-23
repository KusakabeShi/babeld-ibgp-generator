#!/bin/bash

resolveip()
{
  : ${1:?Usage: resolve name}
  (
    PATH=$PATH:/usr/bin
    getent hosts $1 | awk '{print $1}'
  )
}

{% for up in ups -%}
{{ up }}
{% endfor %}
babeld -D -I /var/run/babeld.pid -S /var/lib/babeld/state -c babeld.conf

