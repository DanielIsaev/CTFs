# Nibbles [HTB](https://app.hackthebox.com/machines/Nibbles)
![nibbles-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/nibbles-01.png)

## Recon

After adding the target to my `/etc/hosts` file, i fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- nibbles.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/nmap-res-02.png)

We have the following:

+ An SSH server on port 22.
+ An Apache server on port 80.

Lets take a look at the Apache server and see what we can gather. 


### Apache Port 80

If we open the site at `http://nibbles.htb` we get:

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/site-03.png)

If we take a look at the source code, we can see an interesting comment:

![source-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/source-04.png)

Lets open this directory at `http://nibbles.htb/nibbleblog`:

![blog-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/blog-05.png)

This is a blog site powered by `Nibbleblog`, all links lead to this home page. Lets take a look at the 
source code once again:

![blog-src-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/blog-src-06.png)

Looks like we have an `admin` directory, lets see whats inside:

![admin-dir-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/admin-dir-07.png)

As you can see, I've had a look around and i found the following directory `http://nibbles.htb/nibbleblog/admin/templates/easy4/index.bit`: 

![easy4-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/easy4-08.png)

If you hover over the `Dashboard` link, youll see it outlines the parameters to get the admin login page: 
`http://nibbles.htb/nibbleblog/admin.php?controller=dashboard`

![admin-login-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/admin-login-09.png)

Iv'e tried to hunt down the admin password on the site, i couldnt find it. I also tried to search Google
for the default password, but without success as well. So i decided to brute force it. 

I opened `Burp`, capture a login request and send it to `Intruder`. Here i added the password field:

![intruder-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/intruder-10.png)

I use a `Sniper` attack with `/usr/share/wordlists/john.list` as the password wordlist:

![setup-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/setup-11.png)

I run the attack and i get Blacklisted after 5 attempts:

![blocked-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/blocked-12.png)

So i take a step back and decide to enumerate further with a directory busting scan:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://nibbles.htb/nibbleblog/FUZZ
``` 

The two most interesting results are:

![ffuf-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/blocked-12.png)

![ffuf-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/ffuf-14.png)


The `content` folder has some interesting `xml` files, like `/private/users.xml`, but it doesnt have the 
admin password. If we take a look at the `README` page:

![readme-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/readme-15.png)

We can see the version of the backend CMS. If we search Google, we can find a [public exploit](https://packetstormsecurity.com/files/133425/NibbleBlog-4.0.3-Shell-Upload.html):

![exploit-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/exploit-16.png)

There is also a Metasploit version, but we need the admin credentials. but we cant brute force, so lets try to guess. After a few failed attempts i found the credentials are `admin : nibbles`:

![admin-page-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/admin-page-17.png)

Now that we know the credentials we can try this file upload [exploit](https://github.com/dix0nym/CVE-2015-6967).  We need a PHP reverse shell, i use [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell/blob/master/php-reverse-shell.php)'s

Make sure to update your listener's information:

![update-rshell-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/update-rshell-18.png)

Setup the listner with:

```bash
rlwrap nc -lnvp 443
```

Run the exploit with:

```bash
python3 exploit.py --url http://nibbles.htb/nibbleblog/ --username admin --password nibbles --payload rshell.php
```

This should give you access to the system:

![shell-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/shell-20.png)



## Privilege Escalation


If we check our `sudo` privileges with:

```bash
sudo -l
```

![sudo-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/sudo-21.png)


We can run a bash script located in our home directory as root. But if `cd` into our user's home directory
we see the following:

![home-dir-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/home-dir-22.png)

No `personal` directory, instead we have a zip archive. Lets unzip it:

```bash
unzip personal.zip
```
![unzip-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/unzip-23.png)


Now if check our user's permissions to this script with `ls -l` we can see:

![perms-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/perms-23.png)

We have full read, write and execute permissions to this script. And since we can run it as root via sudo,
we can edit the file to run whatever command we want with elavated privileges. 

I just start a bash session at the end of the script:

```bash
echo "/bin/bash" >> /personal/stuff/monitor.sh
```

And i execute it with sudo:

```bash
sudo /home/nibbler/personal/stuff/monitor.sh
```

![root-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nibbles/img/root-24.png)
