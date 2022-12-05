import yaml
import jinja2
import nacl.public
from base64 import b64encode
from nacl.public import PrivateKey
from ipaddress import  IPv4Network , IPv6Network ,IPv4Address, IPv6Address
from jinja2 import Template, DebugUndefined
from subprocess import Popen, PIPE

psk_db = {}
keypair_db = {}
port_allocate_db = {}
port_allocate_db_i = {}
openvpnkey_db = {}

af_info = {
    "-4":{"MTU":20},
    "-6":{"MTU":40}
}

def vars_load(var):
    print("INFO: loading old state")
    global psk_db
    global keypair_db
    global port_allocate_db
    global port_allocate_db_i
    global openvpnkey_db
    if "psk_db" in var:
        psk_db = var["psk_db"]
    if "keypair_db" in var:
        keypair_db = var["keypair_db"]
    if "port_allocate_db" in var:
        port_allocate_db = var["port_allocate_db"]
    if "port_allocate_db_i" in var:
        port_allocate_db_i = var["port_allocate_db_i"]
    if "openvpnkey_db" in var:
        openvpnkey_db = var["openvpnkey_db"]
        
def vars_dump():
    return {
        "psk_db": psk_db,
        "keypair_db": keypair_db,
        "port_allocate_db": port_allocate_db,
        "port_allocate_db_i": port_allocate_db_i,
        "openvpnkey_db": openvpnkey_db,
    }

def keygen():
    private = PrivateKey.generate()
    return (
        b64encode(bytes(private)).decode("ascii"),
        b64encode(bytes(private.public_key)).decode("ascii"),
    )
def get_psk(id,id2):
    dbkey = (min(id,id2),max(id,id2))
    if dbkey in psk_db:
        return psk_db[dbkey]
    else:
        psk ,_ = keygen()
        psk_db[dbkey] = psk
        return psk_db[dbkey]
    
def get_keypair(id):
    if id in keypair_db:
        return keypair_db[id]
    keypair_db[id] = keygen()
    return keypair_db[id]

def allocate_port(id,id2,port_db,port_base):
    if id not in port_db:
        port_db[id] = { id2: port_base }
        return port_db[id][id2]
    elif id2 not in port_db[id]:
        for p in range(port_base, 65535):
            pfound = False
            for _,usedp in port_db[id].items():
                if p == usedp:
                    pfound = True
                    break
            if pfound == False:
                port_db[id][id2] = p 
                return port_db[id][id2]
    return port_db[id][id2]

def get_wg(server,client):
    conftemplate = Template(open('wg/wg.conf').read(), undefined=DebugUndefined)
    setuptemplate = Template(open('wg/wg.sh').read(), undefined=DebugUndefined)
    server["port"] = 0
    client["port"] = 0
    def renderconf(server,client):
        spri,spub = get_keypair(server["id"])
        cpri,cpub = get_keypair(client["id"])
        if "port" not in server or server["port"] == 0:
            server["port"] = allocate_port(server["name"],client["ifname"],port_allocate_db,server["port_base"]) if server["endpoint"] != "NAT" else 0
        if "port" not in client or client["port"] == 0:
            client["port"] = allocate_port(client["name"],server["ifname"],port_allocate_db,client["port_base_i"]) if client["endpoint"] != "NAT" else 0
        render_params = {
            'wg': {
                'pri': spri, 
                'port': server["port"],
                "pub": cpub,
                "psk": get_psk(server["id"],client["id"]),
                "endpoint": client["endpoint"] + ":" + str(client["port"]) if client["endpoint"] != "NAT" else None
            },
        }
        return conftemplate.render(**render_params)
    def rendersetup(param):
        render_params = {
            "ifname" : param["ifname"]
        }
        return setuptemplate.render(**render_params)
    spri,spub = get_keypair(server["id"])
    cpri,cpub = get_keypair(client["id"])
    conf_s = {
        "up": rendersetup(client),
        "update": f'',
        "reconnect": "",
        "down": "ip link del " + client["ifname"],
        "confs": {".conf": renderconf(server,client) },
        "MTU": 40
    }
    conf_c = {
        "up": rendersetup(server),
        "update": f'wg set { server["ifname"] } peer "{ spub }" endpoint "{ server["endpoint_ip"] + ":" + str(server["port"]) }"',
        "reconnect": f'update_wg_peer { server["ifname"] } "{ spub }" "{ server["endpoint_ip"] + ":" + str(server["port"]) }" "{{{{ confpath }}}}.conf"',
        "down": "ip link del " + server["ifname"],
        "confs": {".conf": renderconf(client,server) },
        "MTU": 40
    }
    return conf_s , conf_c

def get_wg_udp2raw(server,client):
    #print(server,client)
    #return
    server["port"]    = allocate_port(server["name"],client["ifname"],port_allocate_db  ,server["port_base"])
    server["port_wg_local"] = allocate_port(server["name"],client["ifname"],port_allocate_db_i,server["port_base_i"])
    client["port_udp2raw_local"] = allocate_port(client["name"],server["ifname"],port_allocate_db_i,client["port_base_i"])
    server_w = {**server}
    client_w = {**client}
    server_w["endpoint"] = "127.0.0.1"
    server_w["port"] = server["port_wg_local"]
    client_w["endpoint"] = "NAT"
    wg_s, _ = get_wg(server_w,client_w)
    server_w["port"] = client["port_udp2raw_local"]
    _ , wg_c = get_wg(server_w,client_w)
    conf_s, conf_c = wg_s, wg_c
    conf_s["up"] += "\n" + f'udp2raw -s -l 0.0.0.0:{server["port"]} -r 127.0.0.1:{server["port_wg_local"]}  -a -k "{get_psk(server["id"],client["id"])[:10]}" --raw-mode faketcp &'
    conf_s["up"] += '\necho $! > {{ confpath }}.pid'
    conf_c["up"] += "\n" + f'udp2raw -c -r {server["endpoint_ip"]}:{server["port"]} -l 127.0.0.1:{client["port_udp2raw_local"]}  -k "{get_psk(server["id"],client["id"])[:10]}" --raw-mode faketcp -a &'
    conf_c["up"] += '\necho $! > {{ confpath }}.pid'
    conf_s["down"] += '\nkill $(cat {{ confpath }}.pid)'
    conf_c["down"] += '\nkill $(cat {{ confpath }}.pid)'
    conf_s["update"] =  ""
    conf_c["update"] =  "# Not support yet"
    conf_s["reconnect"] = ""
    conf_c["reconnect"] = "# Not support yet"
    conf_s["MTU"] = 140
    conf_c["MTU"] = 140
    return conf_s,conf_c

def get_gre(server,client):
    conf_s = {
        "up": f'ip tunnel add {client["ifname"]} mode gre remote { client["endpoint_ip"] } ttl 255',
        "update": "",
        "reconnect":"",
        "down": "ip link del " + client["ifname"],
        "confs": {},
        "MTU": 4
    }
    conf_c = {
        "up": f'ip tunnel add {server["ifname"]} mode gre remote { server["endpoint_ip"] } ttl 255',
        "update": "",
        "reconnect":"",
        "down": "ip link del " + server["ifname"],
        "confs": {},
        "MTU": 4
    }
    if server["endpoint"] == "NAT":
        raise ValueError(f'Endpoint can\'t be NAT at gre tunnel: { client["id"] } ->  { server["id"] }' )
    if client["endpoint"] == "NAT":
        raise ValueError(f'Endpoint can\'t be NAT at gre tunnel: { server["id"] } ->  { client["id"] }' )
    return conf_s , conf_c

def get_openvpn(server,client):
    server["port"] = allocate_port(server["name"],client["ifname"],port_allocate_db,server["port_base"])
    ovpncfg = get_openvpn_config(server["id"],client["id"])
    conf_s = { 
        "up": f'openvpn --port { server["port"] } --cipher AES-256-CBC --proto tcp-server --dev-type tun --dev { client["ifname"] } --secret $(pwd)/{{{{ confpath }}}}.key --script-security 2 --up $(pwd)/{{{{ setupippath }}}} --writepid $(pwd)/{{{{ confpath }}}}.pid --log /dev/stdout --daemon',
        "update": "",
        "reconnect":"",
        "down": 'kill $(cat {{ confpath }}.pid)',
        "confs": { ".key": ovpncfg["static.key"]  },
        "MTU": 20
    }
    conf_c = {
        "up": f'openvpn --remote { server["endpoint"] } --port { server["port"] } --cipher AES-256-CBC --proto tcp-client --dev-type tun --dev { server["ifname"] } --secret $(pwd)/{{{{ confpath }}}}.key --script-security 2 --up $(pwd)/{{{{ setupippath }}}} --writepid $(pwd)/{{{{ confpath }}}}.pid --log /dev/stdout --daemon',
        "update": "",
        "reconnect":"",
        "down": 'kill $(cat {{ confpath }}.pid)',
        "confs": {  ".key": ovpncfg["static.key"] },
        "MTU": 20
    }
    return conf_s , conf_c
    
def get_openvpn_key(id,id2):
    dictkey = (id,id2)
    if dictkey in openvpnkey_db:
        return openvpnkey_db[dictkey]
    proc = Popen("openvpn --genkey --secret /dev/stdout", shell=True, stdout=PIPE)
    stdout, stderr = proc.communicate()
    if stderr != None and len(stderr) > 0:
        raise Exception(stderr)
    openvpnkey_db[dictkey] = stdout.decode()
    return openvpnkey_db[dictkey]

def get_openvpn_config(id,id2):
    key = get_openvpn_key(id,id2)
    return {
        "static.key" : key
    }
    

def get_v4(id,net):
    first = net[0]
    ip = first + id
    if ip in net:
        return ip
    else:
        raise ValueError(f'{ip} is not in {net}')
def get_v6(id,net):
    first = net[0]
    ip = first + id * (2**64) + 1
    if ip in net:
        return ip
    else:
        raise ValueError(f'{ip} is not in {net}')
def get_v6ll(id,ip):
    return ip + id 

tunnels = {
    None: None,
    "gre": get_gre,
    "wg_udp2raw":get_wg_udp2raw,
    "wg_high":get_wg,
    "openvpn": get_openvpn,
    "wg":get_wg,
    
}

tunnelist = list(tunnels.keys())