#!/bin/bash
babelweb2 -http={{ babeldweb.http }}{% for n in result %} -node=[{{ n.self_ip.v6 }}]:{{ babeldweb.babeld }}{% endfor %}