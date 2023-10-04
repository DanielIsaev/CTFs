# Bank [htb](https://app.hackthebox.com/machines/26)
![bank-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/bank-01.png)

## Recon

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 bank.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/ports-02.png)

Now we can scan these specific ports for more information using:

```bash
nmap -p 22,53,80 -sCV bank.htb -oN namp.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ A DNS server on port 53.
+ An Apache server on port 80.

The site redirected to `login.php`. The DNS server is also interesting, could there be hidden subdomains? Let's start with the DNS server and move on to the Apache right after.


## DNS Port 53

Let's ask the DNS server to return any available entries that it is willing to disclose:

```bash
dig any bank.htb @bank.htb
```

![any-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/any-04.png)

We can see a new subdomain of `chris.bank.htb`, as well as `ns.bank.htb`. I also tried to perfrom zone transfers but that didnt get me much. Let's add the new subdomains to `/etc/hosts` and move on to the Apache server.


## Apache Port 80

Let's start by opening the site at `http://bank.htb` :

![site-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/site-05.png)

We get redirected to `/login.php`. Let's intercept this traffic with Burp:

![intercept-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/intercept-06.png)

We recieve a custom cookie of `HTBBank Auth` from the server. But below that we can also see what seems to be HTML code to render a user's bank account profile:

![html-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/html-07.png)

After that, our own browser makes a request to `login.php`:

![req-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/req-08.png)

This is interesting, I think that we get redirected based on the contents of this cookie. I also noticed that the `php` version here is 5.5.9, which is pretty old. 

If we try to login with some arbitrary credentials we get the following message:

![no-match-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/no-match-09.png)

So we cant enumerate valid email accounts. Let's run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://bank.htb/FUZZ -e .php,.cgi,.js,.txt,.xml,.conf,.html
```

here are some of the notable results:

![ffuf-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/ffuf-10.png)

![ffuf-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/ffuf-11.png)

![ffuf-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/ffuf-12.png)

immediately I went for `uploads` but this gave me a `403` Forbidden response. `inc` returns a list of what seems to be `php` files relevant for the bank application, but I couldn't open any of them. `assets` does return a listing of the directory tree, but there was nothing interesting there. 

I went on to do other enumeration while leaving this running in the background. Until several minutes later, another interesting result came out:

![ffuf-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/ffuf-13.png)

Now this looks very important, if we open this directory we can see the following:

![dir-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/dir-14.png)

As you can see I went ahead and download a couple of the files here. They look something like this:

![example-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/example-15.png)

This is a User's bank account details. But as you can see at the top, it says `++OK ENCRYPT SUCCESS`, all of the information here is cipher text. I wanted to search what kind of encryption this is, so I searched online for information about `acc` files. I found this [page](https://www.reviversoft.com/en/file-extensions/acc#:~:text=ACC%20%5BGraphic%20Accounts%20Data%20File,for%20home%20and%20personal%20accounts.) that describes `acc` files as holding financial detail, produced by the Graphic Accounts application from FKJ Software. 

I tried looking up which encryption this `Graphic Accounts` software uses, but I didnt find anything interesting. And at any case, we dont have the encryption key. So I thought, "maybe there is a file where the encryption failed?"

So I started to go through each file in the `balance-transfer` directory. I've noticed they all are about the same size of around 584 bytes. All of them, except one:

![small-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/small-16.png)

This one is significantly smaller, let's read it:

![creds-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/creds-17.png)

And here we can see the encryption did fail, and we got the creds. Lets log in.


### Authenticated Access

After we login, we can see our victim user's bank account dashboard:

![logged-in-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/logged-in-18.png)

Unfortunately for us, our victim doesnt have a lot of money in his bank account but that's okay. On the surface, it doesnt seem like there is much to do on the main dashboard page, mostly information being dispalyed. But, there is also a `Support` button on the left side, lets click on that.

![support-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/support-19.png)

We can see that we have a file upload feature here. This could be interesting. Let's start by creating a normal support ticket with a `jpg` image and see how it is reflected/handled. 

![prompt-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/prompt-20.png)

We get a nice little animation with this pop-up. In the `My Tickets` window, we can see our newly created ticket:

![ticket-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/ticket-21.png)

We see a link in the `Attachment` column. If we click it, it will redirect us to the `uploads` directry we found earlier:

![uploads-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/uploads-22.png)

So we can access files we upload to the server via the `uploads` directory, the next logical step would be to upload a `php` reverse shell. So I went ahead and used [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell/blob/master/php-reverse-shell.php) php reverse shell, and tried to upload it with a new ticket. This however gave me an error:

![err-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/err-23.png)

The error message says we can only upload images, so we know there is some form of validation happening when we upload files. The question is what form of validation is going on? file extension types? black vs white list?, magic numbers validation? , client vs server side validation? 

So I decided to start with the latter question, I wanted to see if there is any client side validation, so I pressed `F12` to open the developer tools in my browser to go over the source code:

![comment-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/comment-24.png)

We can see a comment saying that `.htb` extensions will be accepted and treated as `php` files. So all we have to do is rename the reverse shell script with:

```bash
mv rshell.php rshell.htb
```

Update our attack machine info in the script:

![update-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/update-25.png)

Start the listener:

```bash
rlwrap nc -lnvp 443
```

Create a ticket, and execute the script at `http://bank.htb/uploads/rshell.htb`.

This stalls my browser, which is a good sign. And on my `nc` listener I get a shell as `www-data`:

![shell-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/shell-26.png)

## Privilege Escalation

After landing on the machine I spwan a TTY shell with:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Then I start to look around the filesystem. I started with the `/var/www` directory tree since we are running as `www-data` and I know there is a subdomain of `chris.bank.htb`, maybe there is something hidden there. 

Unfortunately I didn't find anything super useful in `/var/www`, but inside `/var` I found the `htb` directory:

![dir-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/dir-27.png)

This is rather unusual in `/var`. If we `ls -al` this directory we get the following:

![htb-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/htb-28.png)

This is owned by root, but everyone has read and execute permisions. I decided to read the `emergency` file first:

![emergency-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/emergency-29.png)

This is a very simple Python script. It defines two function, `close()` to exit the program, and the other, `getroot()` runs the `/var/htb/bin/emergency` binary. We cant take a look at a binary, but we can at least check it's permissions:

![perms-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/perms-30.png)

we can see that this binary has the SUID bit set, meanining it will run as root. And it looks like everyone has execute permissions on this binary, so why do we need the previous script for? lets runs this directly:

![root-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/root-31.png)

We can see that the shell prompt has changed to `#` indicating a root shell. But when we run `id` we can see that our UID remained the same, but my effective ID (euid) is now that of root's. 

And this is enough to get the root flag:

![flag-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bank/img/flag-32.png)
