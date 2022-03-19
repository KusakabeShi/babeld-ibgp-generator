#!/usr/bin/python3
import jinja2
import socket
import os
import time
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/var/run/babeld/rw.sock")
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
for line in sockret.split("\n"):
    if "installed yes" in line:
        elem = line.split(" ")[1:]
        data = {}
        for k,v in zip(elem[::2], elem[1::2]):
            data[k] = v
        datakey = data["prefix"].split("/")[0].replace(":","_").replace(".","_")
        datas[datakey] = data["metric"]
print(datas)
ibgptemplate = jinja2.Template(open('bird/ibgp.conf.j2').read())

result=ibgptemplate.render(**datas)

open("bird/ibgp.conf" , "w").write(result)