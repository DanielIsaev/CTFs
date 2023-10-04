# Bank [htb](https://app.hackthebox.com/machines/26)
![bank-01]()

## Recon

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 bank.htb
```

![ports-02]()

Now we can scan these specific ports for more information using:

```bash
nmap -p 22,53,80 -sCV bank.htb -oN namp.result
```

![nmap-res-03]()

We have the following:

+ An SSH server on port 22.
+ A DNS server on port 53.
+ An Apache server on port 80.

We see the site redirected to `login.php`. The DNS server is also interesting, could there be hidden subdomains? Let's start with the DNS server and move on to the Apache right after.


## DNS Port 53

Let's ask the DNS server to return any all the available entries that it is willing to disclose:

```bash
dig any bank.htb @bank.htb
```

![any-04]()

We can see a new subdomain of `chris.bank.htb`, as well as `ns.bank.htb`. I also tried to perfrom zone transfers but that didnt get me much. Let's add the new subdomains to `/etc/hosts` and move on to the Apache server.


## Apache Port 80

Let's start by opening the site at `http://bank.htb` :

![site-05]()

We get redirected to `/login.php`. Let's intercept this traffic with Burp:

![intercept-06]()

We recieve a custom cookie of `HTBBank Auth` from the server. But below that we can also see what seems to be HTML code to render a user's bank account profile:

![html-07]()

After that, our own browser makes a request to `login.php`:

![req-08]()

This is interesting, I think that we get redirected based on the contents of this cookie. I also noticed that the `php` version here is 5.5.9, which is pretty old. 

If we try to login with some arbitrary credentials we get the following message:

![no-match-09]()

So we cant enumerate valid email accounts. Let's run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://bank.htb/FUZZ -e .php,.cgi,.js,.txt,.xml,.conf,.html
```

here are some of the notable results:

![ffuf-10]()

![ffuf-11]()

![ffuf-12]()

immediately I went for `uploads` but this gave me a `403` Forbidden response. `inc` returns a list of what seems to be `php` files relevant  for the bank application, but I couldn't open any of them. `assets` does return a listing of the directory tree, but there was nothing interesting there. 

I went on to do other enumeration while leaving this running in the background. Until several minutes later, another interesting result came out:

![ffuf-13]()

Now this looks very important, if we open this drectory we can see the following:

![dir-14]()

As you can see I went ahead and download a couple of the files here. They look something like this:

![example-15]()

This is a User's bank account details. But as you can see at the top, it says `++OK ENCRYPT SUCCESS`, all of the information we see here is cipher text. I wanted to search what kind of encryption this is, so I searched online for inforamtio about `acc` files. I found this [page](https://www.reviversoft.com/en/file-extensions/acc#:~:text=ACC%20%5BGraphic%20Accounts%20Data%20File,for%20home%20and%20personal%20accounts.) that describes `acc` files as holding financial detail, produced by the Graphic Accounts application from FKJ Software. 

I tried looking up which encryption this `Graphic Accounts` software uses, but I didnt find anything interesting. And at any case, we dont have the encryption key. So I thought, "maybe there is a file where the encryption failed?"

So I started to go through each file in the `balance-transfer` directory. I've noticed they all are about the same size of around 584 bytes. All of them, except one:

![small-16]()

This one is significantly smaller, let's read it:

![creds-17]()

And here we can see the encryption did fail, and we got the creds. Lets log in.


### Authenticated Access

After we login, we can see our victim user's bank account dashboard:

![logged-in-18]()

Unfortunately  for us, our victim doesnt have a lot of money in his bank account but that's okay. On the surface, it doesnt seem like there is much to do on the main dashboard page, mostly information being dispalyed. But, there is also a `Support` button on the left side, lets click on that.

![support-19]()

We can see that we have a file upload feature here. This could be interesting. Let's start by creating a normal support ticket with a `jpg` image and see how it is reflected/handled. 

![prompt-20]()

We get a nice little animation with this pop-up. In the `My Tickets` window, we can see our newly created ticket:

![ticket-21]()

We see a link in the `Attachment` column. If we click it, it will redirect us to the `uploads` directry we found earlier:

![uploads-22]()

So we can access files we upload to the server via the `uploads` directory, the next logical step would be to upload a `php` reverse shell. So I went ahead and used [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell/blob/master/php-reverse-shell.php) php reverse shell, and tried to upload it with a new ticket. This however gave me an error:

![err-23]()

The error message says we can only upload images, so we know there is some form of validation happening when we upload files. The question is what form of validation is going on? file extension types? black vs white list?, magic numbers validation? , client vs server side validation? 

So I decided to start with the latter question, I wanted to see if there is any client side validation, so I pressed `F12` to open the developer tools in my browser to go over the source code:

![comment-24]()

We can see a comment saying that `.htb` extensions will be accepted and treated as `php` files. So all we have to do is rename the reverse shell script with:

```bash
mv rshell.php rshell.htb
```

Update our attack machine info in the script:

![update-25]()

Start the listener:

```bash
rlwrap nc -lnvp 443
```

Create a ticket, and execute the script at `http://bank.htb/uploads/rshell.htb`. This stalls my browser, which is a good sign. And on my `nc` listener I get a shell as `www-data`:

![shell-26]()

## Privilege Escalation

After landing on the machine I spwan a TTY shell with:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Then I start to look around the filesystem. I started with the `/var/www` directory tree since we are running as `www-data` and I know there is a subdomain of `hris.bank.htb`, maybe there is something hidden there. I didn't find anything super useful in `/var/www`, but inside `/var` I found the `htb` directory:

![dir-27]()

This is rather unusual in `/var`. If we `ls -al` this directory we get the following:

![htb-28]()

This is owned by root, but everyone has read and execute permisions. I decided to read the `emergency` file first:

![emergency-29]()

This is a very simple Python script. It defines two function, `close()` to exit the program, and the other, `getroot()` runs the `/var/htb/bin/emergency` binary. We cant take a look at a binary, but we can at least check it's permissions:

![perms-30]()

we can see that this binary has the SUID bit set, meanining it will run as root. And it looks like everyone has execute permissions on this binary, so why do we need the previous script? lets runs this directly:

![root-31]()

We can see that the shell prompt has changed to `#` indicating a root shell. But when we run `id` we can see that our UID remained the same, but my effective ID (euid) is now that of root's. 

And this is enough to get the root flag:

![flag-32]()

