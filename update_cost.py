#!/usr/bin/python3
import jinja2
import socket
import os
import time
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/var/run/babeld/ro.sock")
sock.sendall(b"dump\n")
time.sleep(0.1)
sock.sendall(b"quit\n")
def recvall(sock):
    BUFF_SIZE = 4096
    data = b''
    while True:
        part = sock.recv(BUFF_SIZE)
        data += part
        if len(part) < BUFF_SIZE:
            break
    return data

sockret = recvall(sock).decode("utf8")

datas = {}
neighbors = []
for line in sockret.split("\n"):
    if "installed yes" in line:
        elem = line.split(" ")[1:]
        data = {}
        for k,v in zip(elem[::2], elem[1::2]):
            data[k] = v
        datakey = data["prefix"].split("/")[0].replace(":","_").replace(".","_")
        datas[datakey] = data["metric"]
        neighbors += [{"prefix":data["prefix"] , "metric": data["metric"]}]
print(neighbors)
ibgptemplate = jinja2.Template(open('bird/igp_metric.conf.j2').read())

result=ibgptemplate.render(neighbors = neighbors)

open("bird/igp_metric.conf" , "w").write(result)