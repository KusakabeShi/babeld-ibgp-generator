import yaml
import jinja2
import nacl.public
from base64 import b64encode
from nacl.public import PrivateKey
from ipaddress import  IPv4Network , IPv6Network ,IPv4Address, IPv6Address
from jinja2 import Template, DebugUndefined

psk_db = {}
keypair_db = {}
port_allocate_db = {}

def vars_load(var):
    if "psk_db" in var:
        psk_db = var["psk_db"]
    if "keypair_db" in var:
        keypair_db = var["keypair_db"]
    if "port_allocate_db" in var:
        port_allocate_db = var["port_allocate_db"]
        
def vars_dump():
    return {
        "psk_db": psk_db,
        "keypair_db": keypair_db,
        "port_allocate_db": port_allocate_db
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

def get_wg(server,client):
    conftemplate = Template(open('wg/wg.conf').read(), undefined=DebugUndefined)
    setuptemplate = Template(open('wg/wg.sh').read(), undefined=DebugUndefined)
    def renderconf(server,client):
        spri,spub = get_keypair(server["id"])
        cpri,cpub = get_keypair(client["id"])
        server["port"] = allocate_port(server["name"],client["ifname"],server["port_base"])
        client["port"] = allocate_port(client["name"],server["ifname"],client["port_base"])
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
    n0 = {
        "up": rendersetup(client),
        "down": "ip link del " + client["ifname"],
        "confs": {".conf": renderconf(server,client) }
    }
    n1 = {
        "up": rendersetup(server),
        "down": "ip link del " + server["ifname"],
        "confs": {".conf": renderconf(client,server) }
    }
    return n0 , n1
    
def get_gre(server,client):
    n0 = {
        "up": f'ip tunnel add {client["ifname"]} mode gre remote { client["endpoint"] } ttl 255',
        "down": "ip link del " + client["ifname"],
    }
    n1 = {
        "up": f'ip tunnel add {server["ifname"]} mode gre remote { server["endpoint"] } ttl 255',
        "down": "ip link del " + server["ifname"],
    }
    if server["endpoint"] == "NAT":
        raise ValueError(f'Endpoint can\'t be NAT at gre tunnel: { client["id"] } ->  { server["id"] }' )
    if client["endpoint"] == "NAT":
        raise ValueError(f'Endpoint can\'t be NAT at gre tunnel: { server["id"] } ->  { client["id"] }' )
    return n0 , n1

def get_openvpn(server,client):
    server["port"] = allocate_port(server["name"],client["ifname"],server["port_base"])
    ovpncfg = get_openvpn_config(server["id"],client["id"])
    n0 = {
        "up": 'openvpn --config {{ confpath }}.ovpn &',
        "down": 'kill $(cat {{ confpath }}.pid)',
        "confs": { ".ovpn" : Template(open('ovpn/server.ovpn').read(), undefined=DebugUndefined).render(server=server,client=client),
                  "ca.crt": ovpncfg["ca.crt"],
                  ".crt": ovpncfg["server.crt"],
                  ".key": ovpncfg["server.key"],
                  ".pem": ovpncfg["df.pem"]
                 }
    }
    n1 = {
        "up": 'openvpn --config {{ confpath }}.ovpn &',
        "down": 'kill $(cat {{ confpath }}.pid)',
        "confs": { ".ovpn" : Template(open('ovpn/client.ovpn').read(), undefined=DebugUndefined).render(server=server,client=client),
                  "ca.crt": ovpncfg["ca.crt"],
                  ".crt": ovpncfg["client.crt"],
                  ".key": ovpncfg["client.key"],
                 }
    }
    return n0 , n1
    
def get_openvpn_config(id,id2):
    return {
        "ca.crt" : "aa",
        "server.crt": "bb",
        "server.key": "cc",
        "client.crt": "dd",
        "client.key": "ee",
        "df.pem": ""
    }
    
def allocate_port(id,id2,port_base):
    if id not in port_allocate_db:
        port_allocate_db[id] = { id2: port_base }
        return port_allocate_db[id][id2]
    elif id2 not in port_allocate_db[id]:
        for p in range(port_base, 65535):
            pfound = False
            for _,usedp in port_allocate_db[id].items():
                if p == usedp:
                    pfound = True
                    break
            if pfound == False:
                port_allocate_db[id][id2] = p 
                return port_allocate_db[id][id2]
    return port_allocate_db[id][id2]
def get_v4(id,net):
    first = net[0]
    ip = first + id
    if ip in net:
        return ip
    else:
        raise ValueError(f'{ip} is not in {net}')
def get_v6(id,net):
    first = net[0]
    ip = first + id * (2**64)
    if ip in net:
        return ip
    else:
        raise ValueError(f'{ip} is not in {net}')
def get_v6ll(id,ip):
    return ip + id 

tunnels = {
    None: None,
    "wg":get_wg,
    "openvpn": get_openvpn,
    "gre": get_gre
}

tunnelist = list(tunnels.keys())