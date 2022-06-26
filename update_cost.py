#!/usr/bin/python3
import jinja2
import socket
import os
import time
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/var/run/babeld/ro.sock")

def recvall(sock):
    BUFF_SIZE = 128
    sock.settimeout(1)
    data = b''
    waitmore = 0
    while True:
        part = sock.recv(BUFF_SIZE)
        data += part
        #print(part.decode("utf8") ,end = "")
        if data[-3:].decode("utf8") == "ok\n":
            #print("recvall done")
            return data
        if len(part) < BUFF_SIZE:
            #print(f"partsize={len(part)} wait more")
            if len(part) == 0:
                waitmore += 1
            if waitmore > 5:
                return ""
    return ""

sockret = recvall(sock).decode("utf8")
sock.sendall(b"dump\n")
sockret = recvall(sock).decode("utf8")
sock.sendall(b"quit\n")
#print(sockret)

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
        print( {"prefix":data["prefix"] , "metric": data["metric"]} )
#print(neighbors)
ibgptemplate = jinja2.Template(open('bird/igp_metric.conf.j2').read())

result=ibgptemplate.render(neighbors = neighbors)

open("bird/igp_metric.conf" , "w").write(result)