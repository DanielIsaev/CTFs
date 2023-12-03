# Valentine [HTB](https://app.hackthebox.com/machines/127)

![valentine-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/valentine-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 valentine.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/ports-02.png)


Let's run a version detection scan againts these three ports:

```bash
nmap -p 22,80,443 -sCV valentine.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ An Apache server on ports 80 & 443.


From the `nmap` scans it appears that the target has an Apache server listening on ports 80 & 443, though it dosen't seem like the sites have a title. Also based on the SSH probing scan we can guess that the target is probably a Debian based system. 


Let's have a closer look at this Apache server. 


## Apache Ports 80 & 443

If open the site at `http://valentine.htb/` we will see the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/site-04.png)


Let's check what's powering this site's backend, we can do that with a simple `curl` command:

```bash
curl -s -i http://valentine.htb
```

![powered-by-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/powered-by-05.png)


Looks like the site is running PHP v5.3.10. Worth keeping this in mind as we move forward. 

Based on the `curl` response, we see that the site's main page simply host's this `omg.jpg` image. Other then that, there isn't much to do or see. Let's run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://valentine.htb/FUZZ -e .cgi,.txt,.xml,.html,.php
```

Here are the most relevant results:

![ffuf-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/ffuf-06.png)

![ffuf-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/ffuf-07.png)

![ffuf-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/ffuf-08.png)


I immediately went for the `/dev` directory: 

![dev-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/dev-09.png)


We have two files, a note and a `hype_key` file. Let's start with the note:

![note-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/note-10.png)


The writer of the note refers to an encoder/decoder feature, this matches our directory scan results from the previous step. The writer also mentions that they want the encoder/decoder feature to run on the client side, so we can guess that at the moment it is running on the server side? Could this be a hint for command/code injection?


Let's take a look at the `hype_key` file:

![hype-key-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/hype-key-11.png)


This looks like some sort of cipher, we can try to identify it [here](https://hashes.com/en/tools/hash_identifier):

![hex-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/hex-12.png)


It says that it's a HEX encoded string, we can convert this into ASCII like this:

```bash
curl -s http://valentine.htb/dev/hype_key | xxd -r -p
```

![ascii-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/ascii-13.png)


This looks like a private SSH key, but it seems like the key is encrypted. We can save the key to a local file and try to crack it using `John The Ripper`.


Here is how we can crack encrypted SSH keys with `john`:

```bash
ssh2john hype_key > hype_key.hash
john --wordlist=/usr/share/wordlists/rockyou.txt hype_key.hash
```

Unfortunately no luck:

![john-13.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/john-13.5w.png)


Let's keep the encrypted key for later and move on to test the encoder/decoder application. 


If we open the encoder feature at `http://valentine.htb/encode.php` we can see the following:

![encode-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/encode-14.png)


At this point I opened up Burp Suite and started intercepting traffic to analyze it further. At first I sent a simple `hello` string:

![hello-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/hello-15.png)


We can see that the input is sent to the server via the `text` paramter in a POST request. The result is what looks like a base64 encoded string of the input. 


Another interesting aspect is the fact that our input string is then used in the returned HTML response. This could either be a [Server Side Tameplate Injection](https://book.hacktricks.xyz/pentesting-web/ssti-server-side-template-injection) or an [XSS](https://book.hacktricks.xyz/pentesting-web/xss-cross-site-scripting) vulnerability. 


Let's try to send a simple XSS payload like `<script>alert(1)</script>` :

![xss-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/xss-16.png)


Here we see reflected XSS. Unfortunately, there isn't much to do with this kind of vulnerability in our scnario, as the JavaScript runs on our local browser, not the remote server.  


Then I tried different `SSTI` payloads like `{{7*7}}`, `<%= 7*7 %>`, `{{7/0}}`, and more, trying to idnetify the tameplate enghine, or cause an error, but nothing worked. 


After that I started to think about command/code injection into the encode/decode app. I wasn't sure how the backend is operating on my input. Is it using built in PHP functions like `base64_encode` and `base64_decode`, or is it using something like the `system()` fucntion and passing the inputs to bash? 


I tried numerous approaches and paylods like `a);id`, `|/bin/ls -al`, `;system('cat%20/etc/passwd')`, and many others, in the hope of causing an error, but to no avail. 


At this point I was out of ideas, which means we need to get back to enumeration. So I performed a sub-domain scan with `wfuzz` though nothing came from it. I tried spidering the site but with no luck. I also ran a `nikto` scan but again, no luck.


Instead I decided to use the `nmap`'s vulnerability scanner with:

```bash
nmap --script vuln -p 22,80,443 valentine.htb -oN vuln_scan.nmap
``` 

![vuln-scan-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/vuln-scan-17.png)


The vulnerability scan found several vulnerabilities for the SSL version of the site, the main one in my opinion was this `heartbleed` vulnerability which allows reading the memory of vulenrable systems. 

You can read more about the vulnerability [here](http://www.seancassidy.me/diagnosis-of-the-openssl-heartbleed-bug.html) and [here](http://xkcd.com/1354/).

Let's try it out. 


### HeartBleed 


Let's search for an exploit:

```bash
searchsploit heartbleed
searchsploit -m multiple/remote/32745.py
```

![searchsploit-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/searchsploit-18.png)


To run it we just need to give it the target IP, but it's worth piping the result to `grep` to filter out null bytes:

```bash
python2 32745.py valentine.htb | grep -v "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
```

This spits out a huge amount of output, but at the end we can see the following:

![spits-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/splits-19.png)


Now we need a way to store this memory dump in a file to go over. It will also be best to run it a few times to get as much information as possible, saving the result of each iteration in a seperate file in a dedicated directory.


To achive this we can run something like this:

```bash
mkdir mem_dump
for i in $(seq 1 100); do python2 32745.py valentine.htb | grep -v "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00" > mem_dump/mem_dump$i; done
```

![run-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/run-20.png)


Then we can use `fdupes` to find duplicates and remove them with `xargs`:


```bash
apt install fdupes # If not already installed
cd mem_dump
fdupes -rf . | grep -v '^$' > dupes
xargs -a files rm -v
rm dupes
```


Now we should be left with unique memory dump files:

![unique-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/unique-21.png)


In the second file, `mem_dump2`, I saw the following:

![string-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/string-22.png)


This looks like someone was using the `decode.php` feature to decode the string `aGVhcnRibGVlZGJlbGlldmV0aGVoeXBlCg==`. Let's decode it ourselfes:


```bash
echo 'aGVhcnRibGVlZGJlbGlldmV0aGVoeXBlCg==' | base64 -d
```

![pass-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/pass-23.png)


Could this be the password for the SSH key we found? 


Let's try to login via SSH as the user `hype` with the key we found:


```bash
chmod 400 hype_key 	# Priate SSH keys have to have this permission set.
ssh -i hype_key hype@valentine.htb
```

![ssh-err-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/ssh-err-24.png)


Interesting, never seen this error before when trying to login to ssh... I did a bit of research and I found this [stack-overflow page](https://stackoverflow.com/questions/73795935/sign-and-send-pubkey-no-mutual-signature-supported) which suggest running the command as such:

```bash
ssh -o PubkeyAcceptedKeyTypes=ssh-rsa -i hype_key hype@valentine.htb
```

![shell-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/shell-25.png)


After we supply the password for the key, we are granted access to the system! 


Let's move to privilege escalation. 


## Privilege Escalation


After landing on the machine I start with basic system enumeration. From the `uname -a` output in the above screenshot we can see that the kernel version is `3.2.0-23-generic`. 

Here it is again for reference:

![uname-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/uname-26.png)


From a quick google search we can find that this kernel version is vulnerable to the [DirtyCow](https://dirtycow.ninja/) kernel exploit. This is a good and reliable exploit, but I want to try and find other ways to escalate before resulting to kernel exploits. 


Instead I decided to keep enumerating the target, I searched if there are any other user accounts in `/etc/passwd` but there isn't. I also had a look around our user's home folder but I didn't find anything super useful.


Do I decided to shift gears and take a look at running processes using `ps auxww`, here I found the following: 

![sess-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/sess-30.png)


Looks like root has a `tmux` seesion on the `/.devs/dev_sess` socket. If we research online we will find that there is a privilege escalation path with old tmux versions called `tmux session hijacking`, in which we can attach to running tmux sessions as a low-privliged user if we have read/write permissions to the tmux server socket. 


Let's check our user permissions to the server socket:

![perm-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/perm-31.png)


Looks like we have the necessary permissions via the group `hype`. So we should be able to hijack it. 


Let's try to attach the session to our current window using:

```bash
tmux -S /.devs/dev_sess
```

![tmux-err-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/tmux-err-32.png)


It complains about the `TERM` environment variable missing, we can fix it with:

```bash
export TERM=xterm
tmux -S /.devs/dev_sess
```

Which gives us a tmux session as root:

![root-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/root-33.png)


In root's home folder we can see two files: 

![root-home-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/root-home-34.png)


The `root.txt` file is the flag for the machne, but the `curl.sh` script was interesting to me so I opend it:

![curl-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/curl-35.png)


This is the script that connects to the `decode.php` application and sends the base64 encoded password for `hypes` SSH private key, so we can find it with `heartbleed`. 


If we check `root`'s cron jobs with `crontab -l` we can see the script is being run every 30 seconds:

![crontab-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Valentine/img/crontab-36.png)
