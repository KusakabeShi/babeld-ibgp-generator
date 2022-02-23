babeld-ibgp-generator
====

1. 把 `all_node.yaml`複製到 input 資料夾
2. 把 `generate_config_func.py` 複製到 input 資料夾
3. 修改 `input/all_node.yaml`
4. 執行 `python3 generate_config.py`

all_node.yaml 說明
-----
![image](https://user-images.githubusercontent.com/73118488/155201183-3fd2ed49-3f5b-4d8b-951e-f32de2b65d01.png)  

defaults: 預設值，這個數值會套用到所有節點上，除非在底下改寫  

* port_base: 18000 分配外部端口的起始。 18000 18001 18002 這樣分配下去
* port_base_i: 36000 分配**內部端口**的起始。 36000 36001 36002 ...
* server_perf: 100 雙方都有公網IP的時候，成為server的傾向。數值大的成為server
*  tunnel: 
    *  -1: wg 和目標建立的隧道類型。 -1代表所有目標  

內部端口: wg_udp2raw就需分配一個內部端口，讓wg和udp2raw連線。此端口無須暴露在外網，不用占去寶貴的port forward名額  
外部端口: udp2raw和對面udp2raw連線的端口。此端口需要被port forward  

### tunnel
tunnel則是指定節點之間如何互聯。上面的default指定了，預設使用wg互聯  
紅色: 4-8 之間使用`openvpn`互聯  
黃色: 10-12 之間不互聯  
綠色: 12-`-1` ，也就是12-所有人都使用 `wg_udp2raw` 方式互聯  
![image](https://user-images.githubusercontent.com/73118488/155202813-c9f2dffe-e509-45ae-9e74-db19157e2063.png)  

1-`-1` ，1號節點沒有寫tunnel，所以被套用預設值，{-1:"wg"} ，和所有人使用wg互聯  
此時發生衝突， 1->12 使用`wg`， 12->1 使用`wg_udp2raw`。就會使用優先權高的  

優先權定義在 `generate_config_func.py` 裡面，擺在越上面越優先  
![image](https://user-images.githubusercontent.com/73118488/155201439-af24fdf0-766d-4ab2-8f65-1df85910fc84.png)  

### server_perf
wg是點對點，沒有這個問題，但是openvpn/udp2raw都要一邊做server，一邊做client。  
如果其中一邊是NAT，那就一定是另一邊做server。如果兩邊都是NAT，就不會建立連線  
![image](https://user-images.githubusercontent.com/73118488/155203821-6db252b2-1b86-40f0-a713-d0f1d58d079c.png)  
但如果兩邊都不是NAT，則由 server_perf 數值高的做server ，另一邊做client  
* udp2raw server不支援域名，必須使用IP  
* gre tunnel兩邊都必須使用IP，不能使用域名  

### AF
endpoint裡面有 `-4` 和 `-6` ，可以自訂義增加別的，或是只使用一個。相同AF之間會互相建立。  
以我的例子來說，因為ipv4/ipv6延遲可能不一樣，所以節點間同時建立 ipv4 和 ipv6 連線，由babeld挑選延遲低的走  

generate_config_func.py 說明
------

隧道具體的建立方式，在這邊定義。我目前已經完成 None, "wg" , "wg_udp2raw" , "gre"  
"openvpn"則尚未完成  
![image](https://user-images.githubusercontent.com/73118488/155201953-5587acf5-6ab2-4882-bfb3-cf2b773f1b71.png)  
get_gre / get_wg_udp2raw / get_wg / get_openvpn 四個function會回傳具體的設定檔，up/down腳本  

非常歡迎自訂義新的tunnel種類  
輸入長這樣:  
![image](https://user-images.githubusercontent.com/73118488/155205044-0f306f62-2960-4d6a-9c6c-eb2d41c52d94.png)

返回值是 server 和 client 的設定檔，有 `confs` `up` `down`三個部分  
![image](https://user-images.githubusercontent.com/73118488/155205830-00a1d46d-a867-4175-9fa2-b24081d14049.png)

可以去 `test_func.ipynb` 測試

## Dependance
```
cd ~
apt install -y git babeld wireguard-tools python3-pip net-tools libc-bin gawk
pip3 install -r requirement.txt
wget https://github.com/wangyu-/udp2raw/releases/download/20200818.0/udp2raw_binaries.tar.gz
tar -xvzf udp2raw_binaries.tar.gz -C udp2raw
mv udp2raw/udp2raw_amd64 /usr/bin/udp2raw
```
