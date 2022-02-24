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
tunnel則是指定節點之間如何互聯。  
`?-所有人`: 這個是在`default裡面的值`，意思是`所有人-所有人`使用wg互聯  
![image](https://user-images.githubusercontent.com/73118488/155415520-373420a7-d049-464f-a838-c375758e3d66.png)  
  
紅色: `日本-美國`之間使用`openvpn`互聯  
黃色: `德國-南京`之間不互聯  
綠色: `南京-"-1"`，也就是`南京-所有人`所有人使用 `wg_udp2raw` 方式互聯  
![image](https://user-images.githubusercontent.com/73118488/155202813-c9f2dffe-e509-45ae-9e74-db19157e2063.png)  

此時發生衝突， 1->12 使用`wg`， 12->1 使用`wg_udp2raw`。就會使用優先權高的`wg_udp2raw`   

優先權定義在 `generate_config_func.py` 裡面，擺在越上面越優先  
![image](https://user-images.githubusercontent.com/73118488/155201439-af24fdf0-766d-4ab2-8f65-1df85910fc84.png)  
  
整體來說就是 `美國-日本`用openvpn，`南京-其他人`(跨GFW)用wg_udp2raw，`德國-南京`不連，剩下的使用wg互聯


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

### DDNS
見 Output章節

# Output
生成的結果會放在output資料夾，用name區分每個節點的設定檔。  
![image](https://user-images.githubusercontent.com/73118488/155538861-1333f46b-1422-437f-9bd8-2170e8bfe839.png)
用github/gitee或是什麼方法同步到自己的節點上就可以了

裡面有3個重要的檔案 
#### up.sh
裡面是建立tunnel的指令。請自行加入開機自啟動  
![image](https://user-images.githubusercontent.com/73118488/155537463-eb83eaf7-a9f5-4392-a31f-efbd43a014ec.png)  
以及igp_tunnels資料夾，包含了建立tunnel所需的設定檔。公鑰/私鑰/預共享金鑰都會自動生成  
![image](https://user-images.githubusercontent.com/73118488/155537746-1f8aa0a5-79f3-4962-910c-61bdee0adfeb.png)  

還有最後一行的啟動babeld的指令，執行前請先確認自己的babeld是關閉的  
```
babeld -D -I /var/run/babeld.pid -S /var/lib/babeld/state -c babeld.conf
```

#### down.sh  
第一行關閉babeld，然後刪除自己建立的tunnel  
![image](https://user-images.githubusercontent.com/73118488/155538004-bcd8d43c-bb30-4064-b23e-4d8454475734.png)  
用來一鍵關閉+刪除本腳本建立的tunnel  

#### update.sh  
還記得剛剛的 DDNS=True ，我說`見 Output章節`嗎，這個就是更新wg endpoint的腳本。  
被標記成DDNS=True的節點，會出現在update.sh裡面。  
內容是重新解析域名，指定到wg接口上。 自己把它放在`crontab`就可以了  
![image](https://user-images.githubusercontent.com/73118488/155538122-064677ed-27f8-42c2-88c2-dabdc272824a.png)  


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
![image](https://user-images.githubusercontent.com/73118488/155206208-ddf722ba-a0c0-4ad2-b426-92b1adf21bf1.png)

可以去 `test_func.ipynb` 測試

## Dependance
```
cd ~
apt install -y git babeld wireguard-tools python3-pip net-tools libc-bin gawk ntp
systemctl enable ntp
systemctl start ntp
pip3 install -r requirement.txt
wget https://github.com/wangyu-/udp2raw/releases/download/20200818.0/udp2raw_binaries.tar.gz
tar -xvzf udp2raw_binaries.tar.gz -C udp2raw
mv udp2raw/udp2raw_amd64 /usr/bin/udp2raw
```
