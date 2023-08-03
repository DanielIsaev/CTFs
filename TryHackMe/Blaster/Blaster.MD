# Blaster [THM](https://tryhackme.com/room/blaster)
![blaster-01](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/blaster-01.png)

## Recon

Lets scna the target with:

`nmap -T4 -p- -A -Pn 10.10.151.188 -On nmap.result`

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/nmap-res-02.png)

We have the following:

+ An IIS v10.0 Server on port 80. 
+ RDP on port 3389.


Using `rdesktop` to connect to the target works, but we need credentials to log in. 
Lets take a look at the web server and see what we can gather. 


## IIS 80

Lets open our browser and naviagte towards the site's URL `http://10.10.151.188`

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/site-03.png)


A default IIS page, nothing to interact with. There must be more to this site, 
lets try directory busting: 

`ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt:FUZZ -u http://10.10.151.188/FUZZ`

We get something interesting: 

![ffuf-res-04](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/ffuf-res-04.png)


Lets open this directory:

![retro-05](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/restro-05.png)


The sites displays articals, all written by `wade`. 

If we scroll all the way down we can see a link to a login form. 
I've tried using `sqlmap` and some manual payloads, though they didnt really work for me.  
Decided to have a look around the site instead. 

Found this comments link:

![comments-06](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/comments-06.png)


The link leads to an XML file:

![crerds-07](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/creds-07.png)


I'm thinking creds. 


Which does work for the WordPress: 

![site-own-08](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/site-own-08.png)


But also works for the RDP: 

![init-access-09](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/initial-access-09.png)


With this we can move to priv esc. 


## Privilege Escalation


After connecting to the RDP, i generated `systminfo`:

![sysinfo-10](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/sysinfo-10.png)

The target is a 2016 Win server, 64-bit. I wanted to run `exploit-suggrester` on this file, tried transfering the file via ftp. This failed a timeout, probably something to do with the Active channel. 

Decided to download scp, couldnt install it because our user is not an admin. 

Then, i tried uploading `winpeas` to the target, Windows Defender blocks it. 
We cant change settings since were not an admin. 

Finally i decided to go back to the Desktop, we had an executable there. 

If we write click, and choose `Run as Administrator`, we get prompted for creds:

![uac-11](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/uac-11.png)

We dont have the creds, but we can view the program pulishere's certificate:

![cert-12](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/cert-12.png)


If we click on the `Issued by` link, This should open up a browser to view the cert. 
Since we can browse the local filesystem and execute programs through internet explorer, 
If the susbsequant browser instance is run by the system, we can start a cmd process. 
Check [CVE-2019-1388](https://github.com/nobodyatall648/CVE-2019-1388).  


This happens due to improper permissions checks in the UAC windows Certificate Dialog for certian versions of windows. 

Our target's version is supposed to be vulnerable: 

![vuln-13](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/vuln-13.png)

[source](https://github.com/jas502n/CVE-2019-1388)


if we click the link in the cert, and wait for the page to fully load. 
We can click on `Save as` option:

![save-as-14](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/save-as-14.png)


If we then just type the path to the cmd `C:\\Windows\System32\cmd.exe`:

![path-15](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/path-15.png)

And hit `Enter`, this should open a shell session under `NT_AUTHORITY`:

![root-16](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/Blaster/img/root-16.png)
