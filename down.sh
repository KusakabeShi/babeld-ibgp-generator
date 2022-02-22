#!/bin/bash
kill $(cat /var/run/babeld.pid)


{% for down in downs -%}
{{ down }}
{% endfor %}