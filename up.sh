#!/bin/bash
{% for up in ups -%}
{{ up }}
{% endfor %}
babeld -D -I /var/run/babeld.pid -S /var/lib/babeld/state -c babeld.conf