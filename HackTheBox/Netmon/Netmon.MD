# Netmon [HTB](https://app.hackthebox.com/machines/177)
![netmon-01]()

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 netmon.htb
```

![ports-02]()


I ignore the ports greater then 49K for now, and run a software and version detection scan againts the lower ports:

```bash
nmap -p 21,80,135,139,445,5985,47001 -sCV netmon.htb -oN nmap.result
```

![nmap-res-03]()
![nmap-res-04]()


We have the following:

+ An FTP server on port 21.
+ An Indy HTTP server on port 80.
+ An RPC endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ An SMB sever on port 445.
+ Two HTTPAPI endpoints on ports 5985 & 47001.


All in all, a fairly normal port listing for a Windows box. Scrolling through the list, the most interesting entries in my opinion are the FTP server which allows anonymous logins, and the HTTP server. Then we see `nmap` identified port `5985` to be an HTTPAPI endpoint and not WIN-RM, maybe a false positive? 


Let's start with the FTP server and move on from there. 



### FTP port 21

After logging in with an anonymous session to the FTP, we can see what looks like the listing of the entire `:C\` drive:

![ftp-login-05]()


So I start digging in to every directory, looking in every corner, copying what I think could be useful files over to my attack machine and analyze them. 


Evetually, I reached the `ProgramData` directory, in which I saw an unusual directory:

![program-data-06]()


If we search for the term [paessler](https://en.wikipedia.org/wiki/Paessler_PRTG) online, we will find that it's a network monitoring software developed by Paessler AG. This fits the HTTP title of the site running on port 80, so it immediately caught my attention. 


So my goal becomes finding credentials, I search online for the location of the user passwords of the `PRTG Network Manager` and I find [this reddit post](https://www.reddit.com/r/sysadmin/comments/862b8s/prtg_gave_away_some_of_your_passwords/) which suggested that the credentials should be stored in the `PRTG Configuration.dat` configuraiton file. 


I found a few of these files in the FTP:

![configs-07]()


There was another one located inside an archive at `/ProgramData/Paessler/PRTG Network Monitor/Configuration Auto-Backups/PRTG Configuration (Update to 18.1.37.13946).zip`. 


I copy all the files over to my attack machine and start analyzing them. Inside the `PRTG Configuration.old.bak` file I can see clear-text creds:

![creds-08]()


I try to login to the PRTG portal at `http://netmon.htb` but it fails:

![login-fail-09]()


What? why? 


At this point I got a bit stuck, so I started thinking about the password. We got it from an old backup file, so maybe the new password is `PrTg@dmin2019`? 


I try this one out and it works:

![logged-in-10]()



From here I take a look at the administration panel but there is nothing super intersting there, so instead I start thinking about public exploits. We can see at the buttom of the admin panel that the version of PRTG is `18.1.37.13946`. 


## Exploit To SYSTEM

If we search online, we will find this [authinticated RCE exploit](https://www.exploit-db.com/exploits/46527), which should craete a new admin user upon success. 


In order to run it, we need to supply a few cookies we got after successfully logging in. I copy mine from the FireFox developer tools storage tab. All in all, my syntax looks like this:

```bash
./prtg_rce.sh -u http://netmon.htb -c "_ga=GA1.2.962089491.1704723716; _gid=GA1.2.393625155.1704723716; OCTOPUS1813713946=ezM5MzMwNjBFLUY3NEMtNDlBQS1BOTZDLTM2OTdCQ0IwRkIxNX0%3D; _gat=1"
```

![exploit-11]()


Looks like the exploit worked and a created user with the creds `pentest : P3nT3st!`, let's try to get a shell using `psexec`:

```bash
impacket-psexec pentest:P3nT3st\!@10.129.103.10
```

![root-12]()
