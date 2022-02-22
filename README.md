babeld-ibgp-generator
====

1. Copy `all_node.yaml` to input folder
2. Edit the `all_node.yaml`
3. run `python3 generate_config.py`

## Dependance
```
cd ~
apt install -y git babeld wireguard-tools python3-pip
wget https://github.com/wangyu-/udp2raw/releases/download/20200818.0/udp2raw_binaries.tar.gz
tar -xvzf udp2raw_binaries.tar.gz -C udp2raw
mv udp2raw/udp2raw_amd64 /usr/bin/udp2raw
```