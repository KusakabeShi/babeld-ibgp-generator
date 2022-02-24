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