# Lightweight [HTB](https://app.hackthebox.com/machines/166)
![lightweight-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/lightweight-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 lightweight.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/ports-02.png)


From here I run a software and version detection scan againts the found ports:

```bash
nmap -p 22,80,389 -sCV lightweight.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.6 server on port 80.
+ An LDAP server on port 389.


The most interesting entry on the list is definitely the LDAP service on port 389. The LDAP (Lightweight Directory Access Protocol) software protocol is a **lightweight** version of the DAP protocol. This fits the name of the box thus making it a potential target. 


The LDAP protocol is used to enable anyone to locate organizations, individuals, and other resources such as files and devices in a network, whether on the public internet or on a corporate intranet. Therefore, each LDAP server has a replicated version of the total directory that is synchronized periodically. If the LDAP server is misconfigured, we might be able to extract sensetive data.


Let's have a look! 


### LDAP Port 389


I found [this great artical](https://www.n00py.io/2020/02/exploiting-ldap-server-null-bind/) from `n00py` that outlines a way to enumerate ldap servers via the `ldap3` python module. In case you need to install the module you can run: `pip3 install ldap3`.


To connect to the LDAP server we can open a python shell and use the following sequence:

```python
>>> import ldap3
>>> server = ldap3.Server('10.129.46.132', get_info=ldap3.ALL, port=389, use_ssl=False)
>>> connection = ldap3.Connection(server)
>>> connection.bind()
True
```

The connection was accepted as indicated by the `True` in the output. Now that we have a connection we can try to dump out everything from the server:

```python
>>> connection.search(search_base='DC=lightweight,DC=htb', search_filter='(&(objectClass=*))', search_scope='SUBTREE', attributes='*')
>>> connection.entries
```

![entries-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/entries-04.png)
![entries-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/entries-05.png)


We can see there are two user accounts on the system of `ldapuser1` & `ldapuser2`. Along with these two users, there are also two groups with matching names (as per the Linux convention). We can also see the user's password hashes, which starts with `$6`, indicating it's a `sha512` hash. I tried cracking them both againts `rockyou.txt` with `hashcat` but to no avail. 


At this point I got a bit stuck, I wasn't sure how to furthur enumerate the LDAP server. I tried using `ldapsearch` with several different options, but it gave me similier results. 


At this point I decided to check the Apache server on port 80.


### Apache port 80


If we browse towards `http://lightweight.htb/index.php` we see the following:

![site-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/site-06.png)


I start by clicking on the `Info` button which redirects me to `/info.php`:

![info-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/info-07.png)


The first two sentences are not really helpful. The third sentence does give an interesting hint to avoid using directory fuzzing, as it will lead to a temporary ban. They also supply a link to view any blocked IP's, and at the very end, they give a link to the user page in case you `"want to get in the box"`.


Following this link brings me to `/user.php`:

![user-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/user-08.png)


This page says that we should be able to connect to the SSH server using our IP as the username and password. I follow the instructions and connect to the box:

![box-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/box-09.png)


At first, I started looking around the filesystem, I wanted to see who else is on this server so I read `/etc/passwd`:

![users-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/users-10.png)


We can see the two ldap users, and then we also see two more IP's. One is from the localhost, and the other is from a `10.10.14.2` host. At first, I wasn't sure what to do with this information. I tried to dig around the filesystem some more, but it lead nowhere. I knew that I needed to get access as one of the ldap users but I wasn't sure how. 


Then I went back to the `/user.php` message. It said that `"Your IP (10.10.14.89) is automatically added as userid and password"`, the `uid` part made me think about the LDAP service again. I thought, perhaps we can connect to the LDAP server supplying our IP as credentials and pull new information.


I tried this out with the following command, but it didn't work:

```python
>>> connection = ldap3.Connection(server, 'uid="10.10.14.89",ou=People,dc=lightweight,dc=htb', '10.10.14.89', auto_bind=True)
```

![ldap-err-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/ldap-ee-11.png)


So I decide to dump out the LDAP entires same as before, and I dont see my user of `10.10.14.89`. So it was only added as a user on the target system, not the LDAP database. 


At this point I got a bit stuck, I wasn't sure what I was missing. So I started thinking about the entires in the `/etc/passwd` file again. We know that someone connected to the website via the localhost, so I decided to verify this by running traffic capture with `tcpdump`.


I use the following syntax:

```bash
tcpdump -i lo -nXs 0
```


I wait a couple of minutes but nothing happens, so I start cliking around the website. Once I click on the `status` button I see the following packet:

![packet-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/packet-12.png)


This looks like an LDAP authentication packet. I wasn't sure why this was happeninng, but it got me the clear-text password of `ldapuser2`. 


Which we can now `su` into:

![ldapuser2-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/ldapuser2-13.png)


## Privilege Escalation

If we list the contents of `ldapuser2`'s home directory we can see a `7z` archive:

![archive-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/archive-14.png)


It's also owned by `root` which makes it an even more interesting target. Though copying this archive over to my target was a struggle. 


At first I tried to `cat` the archive to a netcat listener running on my attack machine, but the target doesn't have `nc` installed. Then I start a local FTP server on my attack machine and try to connect from the target, but it doens't have `ftp` installed either.


Then I tried to start a python web server on the tarrget, but I couldn't connect to it from my machine using `wget`, I got a `No route to host` error. I ran `nmap` on the port running the python server and it returned filtered, so maybe a firewall is blocking the connection? I also tried `scp` which faild as well. 


At the end I decided to forward the python server to my attack machine using an SSH tunnel. 


First, I start the python web sever on the target using:

```bash
python -m SimpleHTTPServer 8000
```

Then I start the tunnel on my attack machine using

```bash
ssh -N -L 8000:localhost:8000 "10.10.14.89"@lightweight.htb
```


And finally, I can copy the archive over to my attack machine using:

```bash
wget http://localhost:8000/backup.7z
```

Here it is on my attack machine:

![copied-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/copied-15.png)


If we list the contents of the archive using `7za l backup.7z` we can see the source code for the website:

![list-7z-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/list-7z-16.png)


Currently, we can't navigate towards `/var/www/html`, and read the files there because they are woned by the `apache` service account and we font have permissions. So it could be worth extracting these files nad having a look.


But when we try to extract the archvie we get prompted for credentials:

![7z-err-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/7z-err-17.png)


So I crack the hash with `john` as such:

```bash
7z2john backup.7z > backup.hash
john backup.hash --wordlist=/usr/share/wordlists/rockyou.txt
```

![cracked-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/cracked-18.png)


I extract the archive using `7za x backup.7z`, and I start going over the files. In the `status.php` file I can see the password for `ldapuser1`:

![pass-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/pass-19.png)


That's weird... 


After clickling on the `status` button in the website we got the password of `ldapuser2`, but at any case, the password does work to `su` into `ldapuser1`:

![ldapuser1-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/ldapuser1-20.png)


### ldapuser1

If we list the contents of `ldapuser1` home directory we can see the following:

![home-dir-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/home-dir-21.png)


There are a few interesting files here. The `ldapTLS.php` script has `ldapuser1`'s credentials to what seems like a test script for LDAP over TLS, not super useful. Then we have the `capture.pcap` file, which has an LDAP bind request with `ldapuser2`'s credentials, and some encrypted LDAP traffic. Again, not super interesting. 


But then we have two binaries of `tcpdump` and `openssl`, not something you see in most home folders. If we compare the md5 digest of the files with the original binaries on the system, we can see they are in fact the same:

![same-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/same-22.png)


But checking the capabilities, we can see that for `tcpdump`, they are the same. But for the `openssl` binary in `ldapuser1`'s home folder there is a new capability added:

![cap-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/cap-23.png)


We can abuse this privilege to read the root flag as such:

```bash
./openssl base64 -in /root/root.txt | base64 -d
```

![root-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Lightweight/img/root-24.png)
