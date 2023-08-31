# Beep [htb](https://app.hackthebox.com/machines/5)
![beep-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/beep-01.png)


## Recon

AFter adding the target to our `/etc/hosts` file we can start scanning with `nmap`:

```bash
nmap -sC -sV -A -p- beep.htb -oN nmap.result
```

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/nmap-res-02.png)

We have the following:

+ SSH server on port 22.
+ SMTP server on port 25.
+ Apache on port 80.
+ pop3 email server on port 110.
+ rpcbind on port 111.
+ imap email sever on port 143.
+ Apache server on port 443.
+ imaps on port 993.
+ pop3s on port 995.
+ mysql on port 3306.
+ Asterisk Call Manager on port 5037.
+ MiniServ on port 10000.
+ Other unknown ports at 942, 4190, 4445, 4559.


So we have a very large attack surface here, there are many different things to test. I think its best to
start with port 80 and see what kind of information we can gather from there. Then we can check the emailservers, and the custom applications. 


### Apache Port 80

Lets start by navigating to the target site at `http://beep.htb:80`

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/site-03.png)

If you notice, the site redirected us to an https connection. 

I tried to run directory busting on the web server on both ports 80 and 443, nothing came up. 
I also tested for subdomains, couldnt find any. 

So i decided to move on to the mail servers, we can connect to all servers via telnet, But there isn't 
much to do there without credentials. 


So i decided to go back to the `Elastix` login page, and enumerate further. 

Elastix is a unified communications server software that brings together IP PBX, email, IM, faxing 
and collaboration functionality. It has a Web interface and includes capabilities such as a call 
center software with predictive dialing.

The Elastix 2.5 functionality is based on open source projects including `Asterisk`, `FreePBX`, `HylaFAX`,`Openfire` and `Postfix`. Those packages offer the PBX, fax, instant messaging and email functions, respectively.

If you notice, we have a couple of the above mantioned applications on our target, the `HylaFAX` fax 
server and the `Asterisk` call manager. It all ties together. 

While reading on this tech, i found an interesting exploit on [Github](https://github.com/infosecjunky/FreePBX-2.10.0---Elastix-2.2.0---Remote-Code-Execution/blob/master/exploit.py):

![exploit-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/exploit-04.png)

This looks like Python 2, it appears that the exploit is targeting a vulnerable `callme_page.php` script.
With a special crafted URL payload to land a reverse shell. This is supposed to be an unauthenticated RCE
attack. Lets see if we can find this `callme_page.php` on our target:

`https://beep.htb/recordings/misc/`

![callme-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/callme-05.png)

So far so good, lets try to open the file directly and intercept the `HTTP` traffic with Burp:

![burp-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/burp-06.png)

Looks good, i think its safe to try the exploit. 

After downloading it to your attack machine, make sure to update you `rhost`, `lhost`, 'lport' info:

![info-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/info-07.png)

Now we need to make a couple of changes to our `/etc/ssl/openssl.cnf` file becasue the SSL version on 
our target is pretty old. First back up the file with:

```bash
cp /etc/ssl/openssl.cnf /etc/ssl/openssl.cnf.bak
```

Then at the buttom set the following options: 

![ssl-cnf-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/ssl-cnf-08.png)


Lets start the listener:

```bash
rlwrap nc -lnvp 443
```

Now we can exploit with:

```bash
python2 exploit.py
```

![shell-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/shell-09.png)


## Privilege Escalation


So we have a very limited shell, i treid to upgrade it with various means, didnt work for me, we can work
with this. Lets check for quick wins with `sudo -l`:

![sudo-privs-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/sudo-privs-10.png)

We have quite a lot of programs we can work with, but `nmap` is particlarly interesting because with versions `2.02 - 5.21` we can spwan an interactive shell. Lets check our target's `nmap` version:

[nmap-ver-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/nmap-ver-11.png)


This should be vulnerable. Lets exploit by running:

```bash
sudo nmap --interactive
nmap> !sh
```

![root-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Beep/img/root-12.png)
