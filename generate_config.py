import jinja2
import yaml
import os
import shutil
import string

import ruamel.yaml
from ruamel.yaml.constructor import SafeConstructor

os.umask(0o022)

class PrettySafeLoader(yaml.SafeLoader):
    def construct_python_tuple(self, node):
        return tuple(self.construct_sequence(node))

PrettySafeLoader.add_constructor(
    u'tag:yaml.org,2002:python/tuple',
    PrettySafeLoader.construct_python_tuple)
yaml.Dumper.ignore_aliases = lambda *args : True

if not os.path.isfile("input/all_node.yaml"):
    print("WARN: input/all_node.yaml not found, using default template")
    shutil.copyfile("all_node.yaml", "input/all_node.yaml", follow_symlinks=True)
    
if not os.path.isfile("input/generate_config_func.py"):
    print("WARN: input/generate_config_func.py not found, using default template")
    shutil.copyfile("generate_config_func.py", "input/generate_config_func.py", follow_symlinks=True)

from input.generate_config_func import *
    
gen_conf = ruamel.yaml.safe_load(open("input/all_node.yaml").read())

if os.path.isfile("input/state.yaml"):
    vars_load(yaml.load(open("input/state.yaml").read(), Loader=PrettySafeLoader))

for k,v in gen_conf["node_list"].items():
    gen_conf["node_list"][k]["param"] = {}
    for dk, dv in gen_conf["defaults"].items():
        if dk not in gen_conf["node_list"][k]:
            gen_conf["node_list"][k][dk] = dv
        elif type(dv) == dict:
            gen_conf["node_list"][k][dk] = {**dv, **gen_conf["node_list"][k][dk]}

net4 = IPv4Network(gen_conf["network"]["v4"])
net6 = IPv6Network(gen_conf["network"]["v6"])
net6ll = IPv6Address(gen_conf["network"]["v6ll"])

result = {gen_conf["node_list"][n]["name"]:{"igp_tunnels":{},"bird/ibgp.conf":"","ups":{},"downs":{}} for n in gen_conf["node_list"]}

def get_iface_full(name,af):
    n = gen_conf["iface_prefix"] + name + af
    if len(n) >= 16:
        raise ValueError(f"The interface name: {n} must be less than 16 (IFNAMSIZ) bytes.")
    return n

def get_tun(node, id2):
    if id2 not in node["tunnel"]:
        return node["tunnel"][-1] , 1
    return node["tunnel"][id2] , 0

def get_bash_var_name(strin):
    allowed = set( string.ascii_letters + string.digits + "_" )
    return "".join(map(lambda x: x if x in allowed else "_" , strin))

for id, node in gen_conf["node_list"].items():
    os.makedirs(gen_conf["output_dir"] + "/" + node["name"], exist_ok=True)
    os.makedirs(gen_conf["output_dir"] + "/" + node["name"] + "/igp_tunnels", exist_ok=True)
    os.makedirs(gen_conf["output_dir"] + "/" + node["name"] + "/bird", exist_ok=True)

for id, node in gen_conf["node_list"].items():
    for id2, node2 in gen_conf["node_list"].items():
        if id == id2:
            continue
        ibgptemplate = jinja2.Template(open('bird_ibgp.conf').read())
        result[node["name"]]["bird/ibgp.conf"] += ibgptemplate.render(name = get_bash_var_name(gen_conf["iface_prefix"] + node2["name"]),ip=get_v6(id2,net6))

        for af, end in node["endpoints"].items():
            if af not in node2["endpoints"]: # process only if both side has same af
                continue
            if node["endpoints"][af] == "NAT" and node2["endpoints"][af] == "NAT": # skip if both side are NATed
                continue
            tuntype1, wildcard1 = get_tun(node,id2)
            tuntype2, wildcard2 = get_tun(node2,id)
            if (wildcard1,tunnelist.index(tuntype1)) > (wildcard2,tunnelist.index(tuntype2)):
                tuntype = tuntype2
            else:
                tuntype = tuntype1
            if tuntype1 != tuntype2:
                print("WARN: Tunnel type not match: {s}->{e}:{t1} , {e}->{s}:{t2}, selecting {tun}".format(s=id,e=id2,t1=tuntype1,t2=tuntype2,tun=tuntype))
            if tuntype == None:
                continue
            side_a = {
                **node,
                "id": id,
                "ifname": get_iface_full(node["name"],af),
                "endpoint": node["endpoints"][af],
                "endpoint_ip": "$ip_" + get_bash_var_name(node["name"] + af),
                "params": node["param"][tuntype] if tuntype in node["param"] else None
            }
            side_b = {
                **node2,
                "id": id2,
                "ifname": get_iface_full(node2["name"],af),
                "endpoint": node2["endpoints"][af],
                "endpoint_ip": "$ip_" + get_bash_var_name(node2["name"] + af),
                "params": node2["param"][tuntype] if tuntype in node2["param"] else None
            }
            
            setiptemplate = jinja2.Template(open('setip.sh').read())
            if side_a["endpoint"] == "NAT":
                continue
            try:
                if side_b["endpoint"] == "NAT" or (node["server_perf"],id) >= (node2["server_perf"],id2):
                    aconf, bconf = tunnels[tuntype](side_a,side_b)
                else:
                    bconf, aconf = tunnels[tuntype](side_b,side_a)
                def postprocess(conf,side,idd,nod,side2):
                    conf["up"] = f'{get_bash_var_name(side2["endpoint_ip"][1:])}=$(resolveip {side2["endpoint"]})\n' + conf["up"] if side2["endpoint"] != "NAT" else conf["up"]
                    conf["up"] += "\n" + setiptemplate.render(ifname=side2["ifname"],MTU=nod["MTU"],ipv4=get_v4(idd,net4),ipv6=get_v6(idd,net6),ipv6ll=get_v6ll(idd,net6ll))
                    conf["up"] = jinja2.Template(conf["up"]).render(confpath = "igp_tunnels/" + side2["ifname"])
                    conf["up"] = "\n".join(filter(None,conf["up"].split("\n"))) + "\n"
                    conf["down"] = jinja2.Template(conf["down"]).render(confpath = "igp_tunnels/" + side2["ifname"])
                    
                    for ck,cv in conf["confs"].items():
                        conf["confs"][ck] = jinja2.Template(cv).render(confpath = "igp_tunnels/" + side2["ifname"])
                postprocess(aconf,side_a,id,node,side_b)
                postprocess(bconf,side_b,id2,node2,side_a)
            except ValueError as e:
                print("WARN: " + str(e))
                continue
            if "confs" in aconf:
                result[gen_conf["node_list"][id ]["name"]]["igp_tunnels"][side_b["ifname"]] = aconf["confs"]
            if "confs" in bconf:
                result[gen_conf["node_list"][id2]["name"]]["igp_tunnels"][side_a["ifname"]] = bconf["confs"]
            result[gen_conf["node_list"][id ]["name"]]["ups"][aconf["up"]] = ""
            result[gen_conf["node_list"][id2]["name"]]["ups"][bconf["up"]] = ""
            result[gen_conf["node_list"][id ]["name"]]["downs"][aconf["down"]] = ""
            result[gen_conf["node_list"][id2]["name"]]["downs"][bconf["down"]] = ""

        
for s,sps in result.items():
    for e , confs in sps["igp_tunnels"].items():
        for ext, content in confs.items():
            open(gen_conf["output_dir"] + "/" + s + "/igp_tunnels/" + e + ext , "w").write(content)
    render_params = {
        'allow_ip': {
            'v4': gen_conf["network"]["v4"], 
            'v6': gen_conf["network"]["v6"], 
        },
        'interfaces': list(sps["igp_tunnels"].keys())
    }
    babeldtemplate = jinja2.Template(open('babeld.conf').read())
    babeldconf = babeldtemplate.render(**render_params)
    open(gen_conf["output_dir"] + "/" + s + "/babeld.conf" , "w").write(babeldconf)
    open(gen_conf["output_dir"] + "/" + s + "/up.sh" , "w").write( jinja2.Template(open('up.sh').read()).render(ups = list(sps["ups"].keys())))
    os.chmod(gen_conf["output_dir"] + "/" + s + "/up.sh" , 0o755)
    open(gen_conf["output_dir"] + "/" + s + "/down.sh" , "w").write( jinja2.Template(open('down.sh').read()).render(downs = list(sps["downs"].keys())))
    os.chmod(gen_conf["output_dir"] + "/" + s + "/down.sh" , 0o755)
    open(gen_conf["output_dir"] + "/" + s + "/bird/ibgp.conf" , "w").write(sps["bird/ibgp.conf"])
    
open("input/state.yaml","w").write(ruamel.yaml.dump(vars_dump()))