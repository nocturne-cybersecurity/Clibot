"""Datos del parser: listas grandes de sitios, aplicaciones, servicios y errores comunes.

Formato compacto: ``alias1,alias2=destino`` (una entrada por línea). Se expande al importar.
Añadir algo nuevo es agregar una línea; no hace falta tocar parser.py.
"""
import re


def _table(text, url=False):
    out = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        names, _, target = line.partition('=')
        target = target.strip()
        if url and not target.startswith('http'):
            target = 'https://' + target
        for name in names.split(','):
            if name.strip():
                out[name.strip().lower()] = target
    return out


# ======================================================================
# Sitios web: «abre youtube», «abre mercado libre», «ve a hackthebox»
# ======================================================================
WEB_SERVICES = _table("""
# --- Google
google=www.google.com
google maps,maps,mapas de google=www.google.com/maps
google drive,drive,mi drive=drive.google.com
google docs,docs,documentos de google=docs.google.com
google sheets,sheets,hojas de calculo=sheets.google.com
google slides,slides,presentaciones de google=slides.google.com
google calendar,calendario,calendario de google=calendar.google.com
google fotos,google photos,fotos de google=photos.google.com
google translate,traductor,traductor de google=translate.google.com
google scholar,scholar,google academico=scholar.google.com
google meet,meet=meet.google.com
google earth,earth=earth.google.com
google keep,keep=keep.google.com
google classroom,classroom=classroom.google.com
google forms,formularios de google=forms.google.com
google news,noticias de google=news.google.com
google trends,tendencias=trends.google.com
google cloud,gcp,cloud console=console.cloud.google.com
google analytics,analytics=analytics.google.com
google search console,search console=search.google.com/search-console
google play,play store=play.google.com
google flights,vuelos de google=www.google.com/travel/flights
gmail,correo de google=mail.google.com
youtube,yt=www.youtube.com
youtube music,yt music=music.youtube.com
youtube studio=studio.youtube.com
firebase=console.firebase.google.com
gemini,bard=gemini.google.com
notebooklm=notebooklm.google.com
# --- Buscadores
bing=www.bing.com
duckduckgo,ddg=duckduckgo.com
yahoo=www.yahoo.com
brave search=search.brave.com
ecosia=www.ecosia.org
startpage=www.startpage.com
yandex=yandex.com
baidu=www.baidu.com
searx=searx.be
wolfram alpha,wolframalpha,wolfram=www.wolframalpha.com
# --- Redes sociales y comunidades
facebook,fb=www.facebook.com
instagram,insta,ig=www.instagram.com
twitter=twitter.com
x=x.com
tiktok=www.tiktok.com
snapchat=www.snapchat.com
pinterest=www.pinterest.com
linkedin=www.linkedin.com
reddit=www.reddit.com
tumblr=www.tumblr.com
threads=www.threads.net
mastodon=mastodon.social
bluesky=bsky.app
whatsapp,whatsapp web,wa=web.whatsapp.com
telegram web,telegram online=web.telegram.org
discord=discord.com/app
slack=app.slack.com
twitch=www.twitch.tv
kick=kick.com
vimeo=vimeo.com
dailymotion=www.dailymotion.com
medium=medium.com
quora=www.quora.com
goodreads=www.goodreads.com
flickr=www.flickr.com
deviantart=www.deviantart.com
behance=www.behance.net
dribbble=dribbble.com
imgur=imgur.com
giphy=giphy.com
tenor=tenor.com
pastebin=pastebin.com
telegram=web.telegram.org
signal web=signal.org
# --- Desarrollo
github,gh=github.com
github gists,gists=gist.github.com
github copilot=github.com/features/copilot
gitlab=gitlab.com
bitbucket=bitbucket.org
stackoverflow,stack overflow=stackoverflow.com
serverfault=serverfault.com
superuser=superuser.com
askubuntu,ask ubuntu=askubuntu.com
unix stackexchange,unix=unix.stackexchange.com
hacker news,hackernews,hn=news.ycombinator.com
dev.to,devto=dev.to
codepen=codepen.io
jsfiddle=jsfiddle.net
replit=replit.com
codesandbox=codesandbox.io
stackblitz=stackblitz.com
glitch=glitch.com
vercel=vercel.com
netlify=app.netlify.com
heroku=dashboard.heroku.com
render=dashboard.render.com
railway=railway.app
fly.io,flyio=fly.io
cloudflare=dash.cloudflare.com
digitalocean,digital ocean=cloud.digitalocean.com
aws,amazon web services,aws console=console.aws.amazon.com
azure,azure portal=portal.azure.com
docker hub,dockerhub=hub.docker.com
npm,npmjs=www.npmjs.com
pypi=pypi.org
crates.io,crates=crates.io
packagist=packagist.org
rubygems=rubygems.org
nuget=www.nuget.org
maven central=search.maven.org
mdn,mozilla developer=developer.mozilla.org
w3schools=www.w3schools.com
devdocs=devdocs.io
readthedocs,read the docs=readthedocs.org
python docs,documentacion de python=docs.python.org/3
kaggle=www.kaggle.com
hugging face,huggingface=huggingface.co
colab,google colab=colab.research.google.com
leetcode=leetcode.com
hackerrank=www.hackerrank.com
codewars=www.codewars.com
codeforces=codeforces.com
exercism=exercism.org
freecodecamp,free code camp=www.freecodecamp.org
roadmap.sh,roadmap=roadmap.sh
regex101=regex101.com
jsonlint=jsonlint.com
crontab guru,crontab.guru=crontab.guru
caniuse,can i use=caniuse.com
postman=web.postman.co
swagger=swagger.io
grafana=grafana.com
sentry=sentry.io
datadog=app.datadoghq.com
jira=www.atlassian.com/software/jira
confluence=www.atlassian.com/software/confluence
trello=trello.com
asana=app.asana.com
notion=www.notion.so
clickup=app.clickup.com
monday=monday.com
airtable=airtable.com
linear=linear.app
figma=www.figma.com
canva=www.canva.com
miro=miro.com
lucidchart=lucid.app
draw.io,drawio,diagrams.net=app.diagrams.net
excalidraw=excalidraw.com
mermaid live=mermaid.live
carbon,carbon sh=carbon.now.sh
tailwind,tailwindcss=tailwindcss.com
bootstrap=getbootstrap.com
react docs=react.dev
vue docs=vuejs.org
angular=angular.dev
nextjs,next.js=nextjs.org
nodejs,node.js=nodejs.org
django=www.djangoproject.com
flask=flask.palletsprojects.com
fastapi=fastapi.tiangolo.com
laravel=laravel.com
rust lang,rust=www.rust-lang.org
go lang,golang=go.dev
kotlin=kotlinlang.org
typescript=www.typescriptlang.org
php docs,php=www.php.net
mysql docs=dev.mysql.com/doc
postgresql docs,postgres docs=www.postgresql.org/docs
mongodb atlas=cloud.mongodb.com
supabase=supabase.com
planetscale=planetscale.com
# --- Ciberseguridad
virustotal,virus total=www.virustotal.com
shodan=www.shodan.io
censys=search.censys.io
hackerone=hackerone.com
bugcrowd=bugcrowd.com
intigriti=www.intigriti.com
tryhackme,try hack me,thm=tryhackme.com
hackthebox,hack the box,htb=app.hackthebox.com
overthewire=overthewire.org
portswigger,web security academy=portswigger.net/web-security
owasp=owasp.org
owasp top 10=owasp.org/www-project-top-ten
exploit db,exploitdb,exploit-db=www.exploit-db.com
cve mitre,cve=cve.mitre.org
nvd,nist nvd=nvd.nist.gov
cvedetails,cve details=www.cvedetails.com
mitre attack,att&ck,attack mitre=attack.mitre.org
kali,kali linux=www.kali.org
nmap=nmap.org
wireshark=www.wireshark.org
metasploit docs=docs.metasploit.com
have i been pwned,haveibeenpwned,hibp=haveibeenpwned.com
urlscan=urlscan.io
abuseipdb=www.abuseipdb.com
crt.sh,crtsh=crt.sh
securitytrails=securitytrails.com
any.run,anyrun=any.run
hybrid analysis=www.hybrid-analysis.com
cyberchef=gchq.github.io/CyberChef
pentesterlab=pentesterlab.com
picoctf=picoctf.org
ctftime=ctftime.org
root-me,rootme=www.root-me.org
vulnhub=www.vulnhub.com
sans=www.sans.org
krebs on security,krebs=krebsonsecurity.com
the hacker news=thehackernews.com
bleeping computer,bleepingcomputer=www.bleepingcomputer.com
dark reading=www.darkreading.com
securelist=securelist.com
cisa=www.cisa.gov
cert mx=www.gob.mx/ssc/acciones-y-programas/centro-nacional-de-respuesta-a-incidentes-ciberneticos
gtfobins=gtfobins.github.io
lolbas=lolbas-project.github.io
revshells,reverse shell generator=www.revshells.com
explainshell=explainshell.com
hash cracker,crackstation=crackstation.net
whois=who.is
dnsdumpster=dnsdumpster.com
ssl labs=www.ssllabs.com/ssltest
security headers=securityheaders.com
mxtoolbox=mxtoolbox.com
ipinfo=ipinfo.io
# --- Inteligencia artificial
chatgpt,chat gpt,openai chat=chatgpt.com
openai=openai.com
claude,claude ai=claude.ai
copilot,microsoft copilot=copilot.microsoft.com
perplexity=www.perplexity.ai
mistral,le chat=chat.mistral.ai
poe=poe.com
deepseek=chat.deepseek.com
grok=grok.com
midjourney=www.midjourney.com
stable diffusion=stability.ai
ollama=ollama.com
lm studio=lmstudio.ai
anthropic=www.anthropic.com
# --- Streaming y música
netflix=www.netflix.com
disney plus,disney+=www.disneyplus.com
hbo max,max=www.max.com
prime video,amazon prime video=www.primevideo.com
hulu=www.hulu.com
apple tv=tv.apple.com
crunchyroll=www.crunchyroll.com
vix=vix.com
paramount plus=www.paramountplus.com
pluto tv=pluto.tv
spotify=open.spotify.com
apple music=music.apple.com
deezer=www.deezer.com
soundcloud=soundcloud.com
tidal=tidal.com
bandcamp=bandcamp.com
last.fm,lastfm=www.last.fm
genius,letras=genius.com
imdb=www.imdb.com
letterboxd=letterboxd.com
rotten tomatoes=www.rottentomatoes.com
anilist=anilist.co
myanimelist,mal=myanimelist.net
# --- Compras
amazon=www.amazon.com
amazon mexico,amazon mx=www.amazon.com.mx
mercado libre,mercadolibre,ml=www.mercadolibre.com.mx
ebay=www.ebay.com
aliexpress=www.aliexpress.com
temu=www.temu.com
shein=www.shein.com.mx
walmart=www.walmart.com.mx
liverpool=www.liverpool.com.mx
coppel=www.coppel.com
costco=www.costco.com.mx
home depot=www.homedepot.com.mx
ikea=www.ikea.com/mx
best buy=www.bestbuy.com
newegg=www.newegg.com
steam=store.steampowered.com
epic games,epic=store.epicgames.com
gog=www.gog.com
itch.io,itch=itch.io
cyberpuerta=www.cyberpuerta.mx
ddtech=ddtech.mx
claro shop=www.clarochop.com.mx
elektra=www.elektra.com.mx
soriana=www.soriana.com
rappi=www.rappi.com.mx
uber eats=www.ubereats.com/mx
didi food=web.didiglobal.com/mx/food
doordash=www.doordash.com
# --- Servicios en México
sat=www.sat.gob.mx
imss=www.imss.gob.mx
infonavit=portalmx.infonavit.org.mx
curp=www.gob.mx/curp
gob mx,gobierno de mexico=www.gob.mx
cfe=www.cfe.mx
telmex=telmex.com
telcel,mi telcel=www.telcel.com
izzi=www.izzi.mx
totalplay=www.totalplay.com.mx
banorte=www.banorte.com
bbva,bbva mexico=www.bbva.mx
santander=www.santander.com.mx
citibanamex,banamex=www.banamex.com
hsbc=www.hsbc.com.mx
nu,nubank=nu.com.mx
mercado pago=www.mercadopago.com.mx
paypal=www.paypal.com
bancoppel=www.bancoppel.com
inbursa=www.inbursa.com
scotiabank=www.scotiabank.com.mx
cobaej=www.cobaej.edu.mx
udg,universidad de guadalajara=www.udg.mx
sep=www.gob.mx/sep
jalisco,gobierno de jalisco=www.jalisco.gob.mx
unam=www.unam.mx
ipn=www.ipn.mx
tec de monterrey=tec.mx
uvm=www.uvm.mx
# --- Referencia y noticias
wikipedia,wiki=es.wikipedia.org
wikipedia en ingles,english wikipedia=en.wikipedia.org
wiktionary=es.wiktionary.org
rae,diccionario=www.rae.es
wordreference=www.wordreference.com
linguee=www.linguee.com
deepl=www.deepl.com/translator
archive.org,wayback machine,wayback,internet archive=archive.org
bbc=www.bbc.com
cnn=www.cnn.com
el pais=elpais.com
el universal=www.eluniversal.com.mx
milenio=www.milenio.com
excelsior=www.excelsior.com.mx
nytimes,new york times=www.nytimes.com
the guardian=www.theguardian.com
reuters=www.reuters.com
techcrunch=techcrunch.com
the verge=www.theverge.com
xataka=www.xataka.com
genbeta=www.genbeta.com
ars technica=arstechnica.com
wired=www.wired.com
slashdot=slashdot.org
# --- Correo, nube y oficina
outlook,hotmail=outlook.live.com
yahoo mail=mail.yahoo.com
proton mail,protonmail,proton=mail.proton.me
icloud=www.icloud.com
dropbox=www.dropbox.com
onedrive=onedrive.live.com
mega=mega.nz
box=app.box.com
wetransfer=wetransfer.com
office,microsoft 365,office 365=www.office.com
word online=www.office.com/launch/word
excel online=www.office.com/launch/excel
powerpoint online=www.office.com/launch/powerpoint
teams,microsoft teams=teams.microsoft.com
zoom=zoom.us
skype=web.skype.com
webex=www.webex.com
# --- Utilidades
speedtest,test de velocidad web=www.speedtest.net
fast.com,fast=fast.com
whatismyip,mi ip web=www.whatismyip.com
downdetector=downdetector.com.mx
openstreetmap,osm=www.openstreetmap.org
waze=www.waze.com
bing maps=www.bing.com/maps
weather,clima,el clima=weather.com
accuweather=www.accuweather.com
windy=www.windy.com
timeanddate,time and date=www.timeanddate.com
calculadora online=www.calculator.net
unit converter,convertidor de unidades=www.unitconverters.net
ilovepdf=www.ilovepdf.com
smallpdf=smallpdf.com
remove bg,removebg=www.remove.bg
tinypng=tinypng.com
squoosh=squoosh.app
cloudconvert=cloudconvert.com
online convert=www.online-convert.com
# --- Viajes y transporte
booking=www.booking.com
airbnb=www.airbnb.mx
tripadvisor=www.tripadvisor.com.mx
expedia=www.expedia.mx
skyscanner=www.skyscanner.com.mx
kayak=www.kayak.com.mx
despegar=www.despegar.com.mx
volaris=www.volaris.com
aeromexico=aeromexico.com
viva aerobus,vivaaerobus=www.vivaaerobus.com
uber=m.uber.com
didi=web.didiglobal.com
cabify=cabify.com
indriver=indrive.com
# --- Educación
coursera=www.coursera.org
udemy=www.udemy.com
edx=www.edx.org
khan academy,khanacademy=es.khanacademy.org
platzi=platzi.com
duolingo=www.duolingo.com
codecademy=www.codecademy.com
mit ocw,ocw=ocw.mit.edu
brilliant=brilliant.org
domestika=www.domestika.org
udacity=www.udacity.com
cs50=cs50.harvard.edu
the odin project,odin project=www.theodinproject.com
neetcode=neetcode.io
# --- Hardware y reviews
tomshardware,toms hardware=www.tomshardware.com
notebookcheck=www.notebookcheck.net
techpowerup=www.techpowerup.com
userbenchmark=www.userbenchmark.com
pcpartpicker=pcpartpicker.com
gsmarena=www.gsmarena.com
rtings=www.rtings.com
# --- Linux
ubuntu=ubuntu.com
debian=www.debian.org
arch linux,archlinux=archlinux.org
arch wiki=wiki.archlinux.org
fedora=fedoraproject.org
linux mint,mint=linuxmint.com
manjaro=manjaro.org
opensuse=www.opensuse.org
gentoo=www.gentoo.org
nixos=nixos.org
pop os=pop.system76.com
elementary os=elementary.io
distrowatch=distrowatch.com
phoronix=www.phoronix.com
omg ubuntu,omgubuntu=www.omgubuntu.co.uk
linuxize=linuxize.com
man7,man pages=man7.org/linux/man-pages
tldr=tldr.sh
cheat.sh,cheatsheet=cheat.sh
kernel.org,kernel=www.kernel.org
gnome=www.gnome.org
kde=kde.org
flathub=flathub.org
snapcraft,snap store=snapcraft.io
appimage=appimage.org
ubuntu packages=packages.ubuntu.com
debian packages=packages.debian.org
aur=aur.archlinux.org
# --- Impresión 3D, electrónica y maker
thingiverse=www.thingiverse.com
printables=www.printables.com
cults3d,cults=cults3d.com
myminifactory=www.myminifactory.com
makerworld=makerworld.com
thangs=thangs.com
prusa=www.prusa3d.com
ultimaker cura=ultimaker.com/software/ultimaker-cura
creality=www.creality.com
bambu lab,bambulab=bambulab.com
all3dp=all3dp.com
cgtrader=www.cgtrader.com
sketchfab=sketchfab.com
arduino=www.arduino.cc
raspberry pi,raspberrypi=www.raspberrypi.com
tinkercad=www.tinkercad.com
hackster=www.hackster.io
instructables=www.instructables.com
adafruit=www.adafruit.com
sparkfun=www.sparkfun.com
digikey,digi-key=www.digikey.com.mx
mouser=www.mouser.mx
lcsc=www.lcsc.com
easyeda=easyeda.com
kicad=www.kicad.org
falstad=www.falstad.com/circuit
wokwi=wokwi.com
octoprint=octoprint.org
klipper=www.klipper3d.org
# --- Ajedrez y juegos
chess.com,chesscom,chess=www.chess.com
lichess=lichess.org
chessable=www.chessable.com
chess24=chess24.com
roblox=www.roblox.com
minecraft=www.minecraft.net
""", url=True)


# ======================================================================
# Búsqueda dentro de un sitio: «busca gatos en youtube»
# ======================================================================
SITE_SEARCH = {
    'google': 'https://www.google.com/search?q=', 'duckduckgo': 'https://duckduckgo.com/?q=', 'ddg': 'https://duckduckgo.com/?q=',
    'bing': 'https://www.bing.com/search?q=', 'brave': 'https://search.brave.com/search?q=', 'yahoo': 'https://search.yahoo.com/search?p=',
    'ecosia': 'https://www.ecosia.org/search?q=', 'startpage': 'https://www.startpage.com/do/search?q=',
    'youtube': 'https://www.youtube.com/results?search_query=', 'github': 'https://github.com/search?q=',
    'gitlab': 'https://gitlab.com/search?search=', 'stackoverflow': 'https://stackoverflow.com/search?q=',
    'stack overflow': 'https://stackoverflow.com/search?q=', 'reddit': 'https://www.reddit.com/search/?q=',
    'wikipedia': 'https://es.wikipedia.org/w/index.php?search=', 'amazon': 'https://www.amazon.com.mx/s?k=',
    'mercado libre': 'https://listado.mercadolibre.com.mx/', 'mercadolibre': 'https://listado.mercadolibre.com.mx/',
    'ebay': 'https://www.ebay.com/sch/i.html?_nkw=', 'aliexpress': 'https://www.aliexpress.com/wholesale?SearchText=',
    'spotify': 'https://open.spotify.com/search/', 'twitter': 'https://twitter.com/search?q=', 'x': 'https://x.com/search?q=',
    'linkedin': 'https://www.linkedin.com/search/results/all/?keywords=', 'pinterest': 'https://www.pinterest.com/search/pins/?q=',
    'imdb': 'https://www.imdb.com/find/?q=', 'npm': 'https://www.npmjs.com/search?q=', 'pypi': 'https://pypi.org/search/?q=',
    'docker hub': 'https://hub.docker.com/search?q=', 'maps': 'https://www.google.com/maps/search/', 'google maps': 'https://www.google.com/maps/search/',
    'mapas': 'https://www.google.com/maps/search/', 'google scholar': 'https://scholar.google.com/scholar?q=',
    'google imagenes': 'https://www.google.com/search?tbm=isch&q=', 'imagenes': 'https://www.google.com/search?tbm=isch&q=',
    'google noticias': 'https://news.google.com/search?q=', 'google news': 'https://news.google.com/search?q=',
    'exploit db': 'https://www.exploit-db.com/search?q=', 'exploitdb': 'https://www.exploit-db.com/search?q=',
    'cve': 'https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=', 'nvd': 'https://nvd.nist.gov/vuln/search/results?query=',
    'shodan': 'https://www.shodan.io/search?query=', 'virustotal': 'https://www.virustotal.com/gui/search/',
    'thingiverse': 'https://www.thingiverse.com/search?q=', 'printables': 'https://www.printables.com/search/models?q=',
    'thangs': 'https://thangs.com/search/', 'steam': 'https://store.steampowered.com/search/?term=',
    'netflix': 'https://www.netflix.com/search?q=', 'soundcloud': 'https://soundcloud.com/search?q=',
    'mdn': 'https://developer.mozilla.org/es/search?q=', 'arch wiki': 'https://wiki.archlinux.org/index.php?search=',
    'ubuntu packages': 'https://packages.ubuntu.com/search?keywords=', 'flathub': 'https://flathub.org/apps/search?q=',
    'wolfram alpha': 'https://www.wolframalpha.com/input?i=', 'translate': 'https://translate.google.com/?sl=auto&tl=es&text=',
    'traductor': 'https://translate.google.com/?sl=auto&tl=es&text=', 'deepl': 'https://www.deepl.com/translator#auto/es/',
}


# ======================================================================
# Aplicaciones locales: alias → nombre lógico o comando
# (los valores lógicos como 'terminal', 'browser' o 'gemini_cli' los resuelve el ejecutor)
# ======================================================================
APP_ALIASES = _table("""
# --- Valores lógicos que ya entendía el asistente
metasploit,msfconsole=metasploit
firefox,mozilla firefox,mozilla=firefox
chromium=chromium
chrome,google chrome=chrome
visual studio code,vscode,vs code,vsc,code,visual studio=code
terminal,consola,la terminal,shell grafica=terminal
navegador,browser,el navegador,web browser=browser
editor,editor de texto=editor
pycharm,pycharm community,pycharm professional=pycharm
software,gnome software,centro de software,software center,tienda de aplicaciones,tienda de software=software
mapa,mapas,maps,gnome maps=maps
calculadora,calculator,gnome calculator=calculator
gemini cli,gemini-cli,gemini en terminal=gemini_cli
# --- Navegadores
brave,brave browser,navegador brave=brave-browser
opera,opera browser=opera
vivaldi=vivaldi
edge,microsoft edge,navegador edge=microsoft-edge
tor browser,navegador tor,tor=torbrowser-launcher
librewolf=librewolf
epiphany,gnome web=epiphany
falkon=falkon
qutebrowser=qutebrowser
waterfox=waterfox
zen browser,zen=zen-browser
# --- Editores e IDE
sublime text,sublime=sublime_text
atom=atom
vim=vim
neovim,nvim=nvim
emacs=emacs
nano=nano
micro=micro
gedit,editor de gnome=gedit
kate=kate
kwrite=kwrite
geany=geany
pluma=pluma
mousepad=mousepad
xed=xed
notepadqq=notepadqq
intellij,intellij idea,idea=intellij-idea-community
webstorm=webstorm
clion=clion
goland=goland
rubymine=rubymine
phpstorm=phpstorm
datagrip=datagrip
rider=rider
android studio=android-studio
eclipse=eclipse
netbeans=netbeans
arduino ide,arduino=arduino-ide
thonny=thonny
spyder=spyder
jupyter,jupyter notebook=jupyter-notebook
jupyterlab,jupyter lab=jupyter-lab
rstudio=rstudio
qt creator,qtcreator=qtcreator
code blocks,codeblocks=codeblocks
godot=godot
cursor=cursor
zed=zed
helix=hx
lapce=lapce
kdevelop=kdevelop
gnome builder,builder=gnome-builder
# --- Terminales gráficas
gnome terminal=gnome-terminal
konsole=konsole
xterm=xterm
terminator=terminator
tilix=tilix
alacritty=alacritty
kitty=kitty
wezterm=wezterm
guake=guake
xfce terminal,xfce4 terminal=xfce4-terminal
lxterminal=lxterminal
terminology=terminology
foot=foot
yakuake=yakuake
# --- Multimedia
vlc,reproductor de video,reproductor vlc=vlc
mpv=mpv
totem,videos de gnome=totem
celluloid=celluloid
rhythmbox,reproductor de musica=rhythmbox
audacious=audacious
clementine=clementine
strawberry=strawberry
spotify app,spotify desktop=spotify
kodi=kodi
plex=plexmediaplayer
obs,obs studio,grabador de pantalla=obs
kdenlive=kdenlive
shotcut=shotcut
openshot=openshot-qt
davinci resolve,davinci=davinci-resolve
handbrake=ghb
audacity=audacity
ardour=ardour8
lmms=lmms
musescore=musescore
simplescreenrecorder=simplescreenrecorder
kazam=kazam
peek=peek
flameshot,capturador de pantalla=flameshot
shutter=shutter
gimp,editor de imagenes=gimp
inkscape=inkscape
krita=krita
darktable=darktable
rawtherapee=rawtherapee
digikam=digikam
shotwell=shotwell
visor de imagenes,eye of gnome,eog=eog
gthumb=gthumb
feh=feh
okular=okular
evince,visor de pdf=evince
zathura=zathura
calibre=calibre
foliate=foliate
libreoffice,libre office,suite de oficina=libreoffice
writer,libreoffice writer=lowriter
calc,libreoffice calc,hoja de calculo=localc
impress,libreoffice impress=loimpress
libreoffice draw=lodraw
onlyoffice=onlyoffice-desktopeditors
wps office,wps=wps
thunderbird,cliente de correo=thunderbird
evolution=evolution
geary=geary
kmail=kmail
# --- Archivos y sistema
archivos,nautilus,explorador de archivos,administrador de archivos,files=nautilus
dolphin=dolphin
thunar=thunar
nemo=nemo
pcmanfm=pcmanfm
caja=caja
monitor del sistema,system monitor,gnome system monitor=gnome-system-monitor
ajustes,settings,configuracion,configuracion del sistema,panel de control=gnome-control-center
gnome tweaks,retoques=gnome-tweaks
discos,gnome disks,utilidad de discos=gnome-disks
gparted,particiones=gparted
baobab,analizador de disco,uso de disco grafico=baobab
timeshift=timeshift
bleachbit=bleachbit
synaptic=synaptic
gdebi=gdebi
actualizador de software,update manager,software updater=update-manager
discover,kde discover=plasma-discover
flatseal=com.github.tchx84.Flatseal
extension manager,extensiones de gnome=extension-manager
dconf editor=dconf-editor
blueman,administrador bluetooth,bluetooth manager=blueman-manager
editor de conexiones,nm connection editor=nm-connection-editor
wireshark app=wireshark
virtualbox,virtual box=virtualbox
vmware=vmware
virt manager,virt-manager=virt-manager
gnome boxes,boxes=gnome-boxes
docker desktop=docker-desktop
filezilla=filezilla
remmina=remmina
anydesk=anydesk
teamviewer=teamviewer
keepassxc,keepass=keepassxc
bitwarden=bitwarden
veracrypt=veracrypt
gnome screenshot,captura de pantalla app=gnome-screenshot
copyq,historial del portapapeles=copyq
rofi=rofi
ulauncher=ulauncher
albert=albert
# --- Ciberseguridad y bases de datos
burp suite,burpsuite,burp=burpsuite
owasp zap,zap,zaproxy=zaproxy
ghidra=ghidra
cutter=cutter
autopsy=autopsy
maltego=maltego
ettercap=ettercap-graphical
ida,ida free=ida64
sqlitebrowser,db browser for sqlite,sqlite browser=sqlitebrowser
dbeaver=dbeaver
pgadmin=pgadmin4
mysql workbench=mysql-workbench
mongodb compass=mongodb-compass
redis insight,redisinsight=redisinsight
postman app=postman
insomnia=insomnia
bruno=bruno
cherrytree=cherrytree
obsidian=obsidian
joplin=joplin
logseq=logseq
zettlr=zettlr
typora=typora
standard notes=standard-notes
simplenote=simplenote
# --- Comunicación
discord app,discord desktop=discord
slack app,slack desktop=slack
telegram desktop,telegram app,telegram=telegram-desktop
whatsapp app,whatsapp desktop=whatsapp-for-linux
signal,signal desktop=signal-desktop
element,element chat=element-desktop
zoom app,zoom desktop=zoom
microsoft teams app=teams
skype for linux,skype app=skypeforlinux
# --- Impresión 3D y diseño técnico
cura,ultimaker cura app=cura
prusaslicer,prusa slicer=prusa-slicer
orcaslicer,orca slicer=orca-slicer
bambu studio=bambu-studio
freecad=freecad
openscad=openscad
meshlab=meshlab
blender=blender
librecad=librecad
fritzing=fritzing
kicad app=kicad
qcad=qcad
sweet home 3d=sweethome3d
# --- Juegos
steam app,steam desktop=steam
lutris=lutris
heroic,heroic games launcher=heroic
bottles=bottles
retroarch=retroarch
prism launcher,prismlauncher=prismlauncher
minecraft launcher=minecraft-launcher
gnome chess,ajedrez=gnome-chess
pychess=pychess
scid vs pc,scid=scid
# --- Utilidades de escritorio
calendario de gnome,gnome calendar=gnome-calendar
reloj,relojes,gnome clocks=gnome-clocks
clima de gnome,gnome weather=gnome-weather
contactos,gnome contacts=gnome-contacts
mapa de caracteres,character map=gnome-characters
fuentes,visor de fuentes=gnome-font-viewer
contrasenas,seahorse,llaves=seahorse
""")

# Herramientas de terminal: se abren dentro de una terminal nueva.
TERMINAL_TOOLS = _table("""
htop=htop
btop=btop
bpytop=bpytop
top=top
glances=glances
nmon=nmon
atop=atop
iotop=iotop
nethogs=nethogs
iftop=iftop
bmon=bmon
nload=nload
ncdu=ncdu
midnight commander,mc=mc
ranger=ranger
nnn=nnn
tmux=tmux
screen=screen
cmus=cmus
weechat=weechat
irssi=irssi
w3m=w3m
lynx=lynx
neofetch=neofetch
fastfetch=fastfetch
cmatrix=cmatrix
cava=cava
lazygit=lazygit
lazydocker=lazydocker
k9s=k9s
ctop=ctop
dstat=dstat
bandwhich=bandwhich
zenith=zenith
gtop=gtop
vtop=vtop
nvtop=nvtop
powertop=powertop
mtr=mtr
tcpdump=tcpdump
python,python3,interprete de python=python3
ipython=ipython
node repl=node
sqlite3=sqlite3
mysql cli=mysql
psql=psql
redis-cli=redis-cli
""")


# ======================================================================
# Servicios del sistema (systemd) y sus nombres alternativos
# ======================================================================
SYSTEM_SERVICES = (
    'nginx', 'apache2', 'apache', 'httpd', 'lighttpd', 'caddy', 'haproxy', 'traefik', 'varnish', 'squid', 'tomcat',
    'tomcat9', 'jetty', 'ssh', 'sshd', 'postgresql', 'mysql', 'mysqld', 'mariadb', 'mongod', 'mongodb', 'redis',
    'redis-server', 'memcached', 'cassandra', 'elasticsearch', 'kibana', 'logstash', 'influxdb', 'grafana-server',
    'prometheus', 'node_exporter', 'alertmanager', 'telegraf', 'zabbix-agent', 'zabbix-server', 'nagios',
    'rabbitmq-server', 'kafka', 'zookeeper', 'docker', 'containerd', 'podman', 'libvirtd', 'virtlogd', 'kubelet', 'k3s',
    'cron', 'crond', 'anacron', 'atd', 'rsyslog', 'systemd-journald', 'systemd-resolved', 'systemd-networkd',
    'systemd-timesyncd', 'systemd-logind', 'NetworkManager', 'wpa_supplicant', 'dhcpcd', 'dnsmasq', 'bind9', 'unbound',
    'isc-dhcp-server', 'avahi-daemon', 'bluetooth', 'cups', 'cups-browsed', 'ufw', 'firewalld', 'fail2ban', 'apparmor',
    'auditd', 'clamav-daemon', 'clamav-freshclam', 'openvpn', 'wireguard', 'tor', 'nftables', 'sshguard', 'smbd', 'nmbd',
    'samba', 'smb', 'nmb', 'nfs-server', 'nfs-kernel-server', 'vsftpd', 'proftpd', 'pure-ftpd', 'postfix', 'dovecot',
    'exim4', 'opendkim', 'sendmail', 'gdm', 'gdm3', 'lightdm', 'sddm', 'display-manager', 'accounts-daemon', 'polkit',
    'udisks2', 'upower', 'thermald', 'tlp', 'power-profiles-daemon', 'acpid', 'irqbalance', 'smartd', 'snapd',
    'packagekit', 'unattended-upgrades', 'ntp', 'ntpd', 'chrony', 'chronyd', 'dbus', 'pulseaudio', 'pipewire',
    'pipewire-pulse', 'wireplumber', 'jenkins', 'gitlab-runner', 'sonarqube', 'minio', 'supervisor', 'supervisord',
    'php-fpm', 'php8.3-fpm', 'php8.2-fpm', 'php8.1-fpm', 'php7.4-fpm', 'uwsgi', 'gunicorn', 'celery', 'ollama',
    'jellyfin', 'plex', 'pihole-FTL', 'syncthing', 'transmission-daemon', 'qbittorrent-nox', 'cockpit', 'webmin',
    'teamviewerd', 'x11vnc', 'xrdp', 'lxd', 'mdadm', 'fwupd', 'colord', 'geoclue', 'ModemManager', 'cloud-init',
    'sssd', 'slapd', 'freeradius', 'mosquitto', 'node-red', 'octoprint', 'klipper', 'moonraker', 'portainer',
    'homeassistant', 'nextcloud', 'vault', 'consul', 'nomad', 'etcd', 'loki', 'promtail', 'rpcbind', 'cockroach',
)
SERVICE_WORDS = r'(?:' + '|'.join(re.escape(n) for n in sorted(set(SYSTEM_SERVICES), key=len, reverse=True)) + r')'

# Lo que el usuario escribe → nombre canónico de la unidad (services.resolve_unit resuelve el resto).
SERVICE_NAME_MAP = {
    'apache': 'apache2', 'httpd': 'apache2', 'ssh': 'ssh', 'mongodb': 'mongod', 'postgres': 'postgresql',
    'grafana': 'grafana-server', 'rabbitmq': 'rabbitmq-server', 'networkmanager': 'NetworkManager',
    'network manager': 'NetworkManager', 'samba': 'smbd', 'php-fpm': 'php-fpm', 'nfs': 'nfs-server',
    'mariadb': 'mariadb', 'node exporter': 'node_exporter', 'pihole': 'pihole-FTL', 'wireguard': 'wg-quick@wg0',
}

# Servidores que "se levantan": palabras que, junto a un verbo de arranque, disparan services.change start.
SERVER_DAEMONS = (
    'apache2', 'apache', 'httpd', 'nginx', 'lighttpd', 'caddy', 'tomcat', 'haproxy', 'traefik', 'varnish', 'squid',
    'mysql', 'mariadb', 'postgresql', 'postgres', 'redis', 'mongodb', 'mongod', 'memcached', 'elasticsearch',
    'rabbitmq', 'kafka', 'influxdb', 'grafana', 'prometheus', 'ssh', 'sshd', 'vsftpd', 'proftpd', 'samba', 'postfix',
    'dovecot', 'bind9', 'dnsmasq', 'openvpn', 'wireguard', 'docker', 'jenkins', 'minio', 'ollama', 'jellyfin',
    'mosquitto', 'cockpit', 'webmin', 'php-fpm', 'uwsgi', 'gunicorn', 'supervisor', 'syncthing',
)


# ======================================================================
# Errores tipográficos de búsqueda: «correcto:typo1,typo2»
# ======================================================================
def _typos(text):
    out = {}
    for line in text.strip().splitlines():
        if ':' in line:
            right, _, wrong = line.partition(':')
            out[right.strip()] = [w.strip() for w in wrong.split(',') if w.strip()]
    return out


TYPO_TERMS = _typos("""
python:piton,pyton,phyton,pythn,pyhton,pithon
javascript:javascrit,javascrip,javscript,java script,javasript
typescript:typscript,typescrip,tipescript,typesript
java:jaba,yava
kotlin:kotlyn,cotlin,kotln
swift:swfit,suift
golang:golan,gollang,go lang
rust:rrust,rsut,russt
php:phph,pph
ruby:rubi,rubby
bash:bsh,bahs,vash
powershell:powrshell,powershel,power shell
linux:linus,linx,lunix,linuxx,liux
ubuntu:ubunto,ubunbtu,ubutu,ubuntoo,ubunut
debian:debain,debia,devian
fedora:fedroa,fedor,fedoraa
arch linux:archlinux,arch linx,arc linux
kali linux:kali linus,kalilinux,cali linux
windows:window,windos,windwos,wndows
macos:mac os,maxos,macoss
android:andriod,androind,andorid
docker:doker,docer,dokcer,dockr
kubernetes:kubernets,kuberntes,kubernete,k8
git:gitg,gitt,gti
github:githun,githab,gitub,guithub,gihub
gitlab:gitlba,gitlap,gitlab.
stackoverflow:stackoverfow,stak overflow,stackoverlow
nginx:ngnix,nginix,enginx,ngnx
apache:apach,apche,apahce
mysql:mysqll,mysq,my sql,maysql
postgresql:postgre,postgress,postgres sql,postgesql
mongodb:mongo db,mongodv,mogodb
redis:reddis,redi,redys
sqlite:sqlit,sqlite3,esqlite
nmap:nmpa,nmapp,namp
wireshark:wiresark,wireshak,wire shark
metasploit:metasploi,metaploit,metasplot
burpsuite:burp suit,burpsuit,burpsuite
virustotal:virus total,virustotl,virustotall
shodan:shoodan,shodna,shodann
cybersecurity:ciberseguridad,cyber security,cybersecurty
pentesting:pentestin,pen testing,pentestng
hackthebox:hack the box,hackthebo,hackthebx
tryhackme:try hack me,tryhackm,tryhackeme
vpn:vnp,vpm
firewall:firewal,fire wall,firewal
wordpress:wordpres,word press,wordpress
html:htlm,htm,hmtl
css:ccs,csss
react:reac,raect,reakt
angular:angullar,anguler,angualr
vue:vuejs,vew
node:nodo,nod
nodejs:node js,nodeejs,nodjs
tensorflow:tensor flow,tensorflo,tensorfow
pytorch:py torch,pytorc,pitorch
pandas:panda,pandsa
numpy:numpi,numpyy,nunpy
jupyter:jupiter,jupyer,jupyterr
chatgpt:chat gpt,chatgtp,chatgpt,chatgp
claude:clode,claud,clause,cloude
gemini:gemni,geminy,gemin
openai:open ai,openia,opneai
google:gogle,googl,gugle,goolge,gooogle
gmail:gmial,gmai,gmal,gmaill
youtube:youtub,youttube,yutube,youtubee,yotube
facebook:facebok,facebool,feisbuk,facebokk
instagram:instagra,instragram,instagran,instagramm
twitter:twiter,tweeter,twiteer,twitterr
tiktok:tik tok,tiktk,tiktokk
whatsapp:whatsap,wasap,watsapp,whastapp,whatssap
telegram:telegran,telgram,telegrm
discord:discor,dicord,discrod
spotify:spotif,spootify,spotyfy,spotfy
netflix:netfix,netflixx,netfliks
amazon:amzon,amazzon,amazom,amazn
mercado libre:mercadolibre,mercado libr,mercadolibr
microsoft:microsft,microsof,micosoft,microsoftt
apple:aple,appl,appel
samsung:samsun,samsng,samsumg
huawei:huawey,huaweii,huaweii
xiaomi:xiaomy,xaomi,xiomi,xiaomii
intel:intell,inte,intl
amd:amdd,am,ad
nvidia:nvidi,nvidda,nividia,nvdia
raspberry pi:raspbery pi,rasberry pi,raspberrypi,raspberi pi
arduino:arduinio,ardunio,arduin
esp32:esp 32,esp-32,esp3
thingiverse:thingverse,thingiverze,tingiverse
printables:printable,printabels
blender:blendr,blnder,blenderr
freecad:free cad,freecadd,frecad
openscad:open scad,openscadd,openscd
inkscape:inkscap,inkscpe,inkscaep
gimp:gimpp,gmp
libreoffice:libre office,libreofice,libre ofice
obsidian:obsidan,obsidia,obsydian
notion:notin,notio,nocion
trello:trelo,trelloo,trelo
slack:slak,slakc,slacc
zoom:zom,zooom
teams:tems,teamz
outlook:outlok,outlook.,outlock
dropbox:dropbx,dropbo,drobox
onedrive:one drive,onedriv,onedrve
wikipedia:wikipedea,wikipedi,wikipdia,wikipeda,wikiepdia
duckduckgo:duck duck go,duckduckg,ducduckgo
bing:bign,bingg
yahoo:yaho,yahooo,yajoo
reddit:redit,redditt,redit
twitch:twich,twitc,twitchh
steam:steem,steamm,stean
epic games:epic gams,epicgames,epic gamess
minecraft:minecrft,minecraf,maincraft,minecrat
roblox:roblos,robloks,robblox
fortnite:fornite,fortnit,fortnitee
chess:ches,chesss,ajedres
lichess:liches,lichesss,li chess
ssh:shh,sssh,ssh.
telnet:telne,telnnet,telent
ftp:ftpp,fpt
dns:dnss,dsn
dhcp:dhpc,dhcpp,dhc
tcp:tpc,tcpp
udp:upd,udpp
http:htttp,htp,htpp
https:htttps,htps,httsp
ssl:sll,ssll
tls:tsl,tlss
ipv4:ip v4,ipv 4,ipvv4
ipv6:ip v6,ipv 6,ipvv6
subnet:subnt,subnett,subred
router:ruter,rooter,routr
switch:swich,swithc,swtich
vlan:valn,vlann,v lan
nat:natt,nta
iptables:ip tables,iptable,iptabels
ufw:uwf,ufww
fail2ban:fail 2 ban,fail2ba,failtoban
tcpdump:tcp dump,tcpdum,tcpdmp
netcat:net cat,netca,netcatt
curl:cur,culr,curll
wget:wge,wgett,wgeet
rsync:rsinc,rsyn,rsyncc
tmux:tmuks,tmx,tmuxx
vim:vimm,vmi
neovim:neo vim,neovi,nevim
emacs:emac,emacss,emaxs
nano:nanoo,nan
htop:htpo,htopp,hotp
systemd:system d,systmd,systemdd
journalctl:journal ctl,journalct,journactl
crontab:cron tab,crontb,crontabb
chmod:chmdo,chmood,chmodd
chown:chonw,chwon,chownn
sudo:suod,sudoo,sdo
apt:aptt,atp
snap:snapp,snp
flatpak:flat pak,flatpack,flatpakk
pip:pipp,ppi
npm:nmp,npmm,npn
cargo:cargoo,cagro
make:mkae,makee
cmake:c make,cmak,cmakee
gcc:gccc,gc
clang:clan,clangg
llvm:lvmm,llvmm
assembly:asembly,assemly,ensamblador
sql:sqll,sq
nosql:no sql,nosqll
graphql:graph ql,graphq,graphqll
rest api:restapi,rest ap,reast api
json:jsno,jsonn,jason
yaml:yml,yamll,yaaml
xml:xlm,xmll
markdown:markdwon,markdow,markdonw
latex:latx,latexx,late x
overleaf:overlef,overleaff,over leaf
figma:figam,figmaa,fgima
canva:canba,canvaa,cnva
photoshop:fotoshop,photoshp,photoshopp
illustrator:ilustrator,ilustrador,illustrtor
premiere:premier,premiere pro,premire
davinci resolve:davinci resolv,da vinci resolve,davinchi
audacity:audacidad,audacty,audaciti
vlc:vcl,vllc
obs:osb,obss
telegram desktop:telegram desktp,telegran desktop
mozilla:mozila,mosilla,mozzila
firefox:firfox,firefx,firefoz,fire fox,firefix
chrome:crome,chorme,chromee,chrom
chromium:cromium,chromiun,chromuim
brave:brav,bravee
opera:oprea,operaa
edge:egde,edgee
safari:safri,safarii
tor:torr,tro
proton:protn,protonn
bitwarden:bitwardn,bitwarde,bit warden
keepass:kepass,keepas,keepasss
veracrypt:vera crypt,veracript,veracryp
openvpn:open vpn,openvp,openvpnn
wireguard:wire guard,wireguar,wireguardd
virtualbox:virtual box,virtualbx,virtualboc
vmware:vm ware,vmwar,vmwre
qemu:qemmu,qemuu,quemu
vagrant:vagran,vagrnt,vagrantt
ansible:ansibl,ansibel,ansibble
terraform:teraform,terrafom,terraformm
jenkins:jenkin,jenkinss,jenkis
grafana:grafna,grafanna,graphana
prometheus:promethius,prometeus,promotheus
elasticsearch:elastic search,elasticsearh,elastisearch
kibana:kibna,kibanna,kibaana
splunk:splunck,splunkk,splnk
wazuh:wazu,wazhu,wazuhh
snort:snor,snortt,snrot
suricata:suricta,suricatta,suricat
zeek:zek,zeeck,zeekk
openssl:open ssl,opensl,openssll
gpg:gppg,gpgg,pgp
hashcat:hash cat,hashct,hashcatt
john the ripper:johntheripper,john the ripr,jhon the ripper
aircrack:air crack,aircrak,aircrack-ng
hydra:hidra,hydraa,hydrra
sqlmap:sql map,sqlmapp,sqlmp
nikto:nicto,niktto,nikt
gobuster:go buster,gobustr,gobusterr
ffuf:ffu,fuff,ffufff
dirb:dirbb,drib
wpscan:wp scan,wpscann,wpscna
searchsploit:search sploit,searchsploi,serchsploit
maltego:maltgo,maltego.,malteg
autopsy:autopsi,autopsyy,autopsie
volatility:volatilty,volatilidad,volatiliy
ghidra:gidra,ghydra,ghidraa
radare2:radar2,radare,radar e2
cutter:cuter,cutterr
ollydbg:olly dbg,ollydb,olydbg
gdb:gddb,gbd
strace:s trace,stracee,straace
ltrace:l trace,ltracee,ltrcae
wireguard vpn:wireguardvpn,wireguard vp
""")

# ======================================================================
# Verbos y palabras comunes mal escritas (se corrigen antes de aplicar las reglas)
# ======================================================================
WORD_FIXES = {
    # abrir
    'abrre': 'abre', 'abrr': 'abre', 'abir': 'abrir', 'abrirr': 'abrir', 'abrime': 'abre', 'abreme': 'abre',
    'abrilo': 'abre', 'abrelo': 'abre', 'abri': 'abre', 'habre': 'abre', 'habrir': 'abrir', 'abrie': 'abre',
    # ejecutar
    'ejecutra': 'ejecuta', 'ejecuuta': 'ejecuta', 'ejectua': 'ejecuta', 'ejecutar': 'ejecuta', 'ejecutalo': 'ejecuta',
    'ejeucta': 'ejecuta', 'exeuta': 'ejecuta', 'corre': 'corre', 'correr': 'corre', 'correlo': 'corre',
    # crear
    'crera': 'crea', 'creaa': 'crea', 'craer': 'crear', 'creear': 'crear', 'crar': 'crear', 'creame': 'crea',
    'hazme': 'crea', 'generame': 'genera',
    # borrar / eliminar
    'borar': 'borrar', 'borra': 'borra', 'borrra': 'borra', 'boorra': 'borra', 'elimna': 'elimina', 'eliminaa': 'elimina',
    'elminar': 'eliminar', 'eliminar': 'eliminar', 'borralo': 'borra', 'eliminalo': 'elimina', 'suprime': 'elimina',
    # mostrar
    'muestrame': 'muestra', 'muestramelo': 'muestra', 'muestra': 'muestra', 'mostrame': 'muestra', 'mustra': 'muestra',
    'mostar': 'mostrar', 'ensename': 'muestra', 'enseñame': 'muestra', 'dime': 'dime', 'dimee': 'dime', 'pasame': 'muestra',
    'listame': 'lista', 'listar': 'listar', 'lsita': 'lista', 'lista': 'lista', 'enlista': 'lista', 'enumera': 'lista',
    # servicios
    'reinicai': 'reinicia', 'reiniciaa': 'reinicia', 'renicia': 'reinicia', 'reinisia': 'reinicia', 'reiniciar': 'reiniciar',
    'reinciar': 'reiniciar', 'reinicialo': 'reinicia', 'resetea': 'reinicia', 'resetear': 'reiniciar', 'rebootea': 'reinicia',
    'detner': 'detener', 'detenr': 'detener', 'deten': 'deten', 'detenlo': 'deten', 'frena': 'deten', 'frenar': 'detener',
    'inicai': 'inicia', 'iniciaa': 'inicia', 'iniciar': 'iniciar', 'inicialo': 'inicia', 'comienza': 'inicia',
    'levanta': 'levanta', 'levantar': 'levantar', 'levantalo': 'levanta', 'lebanta': 'levanta', 'lebantar': 'levantar',
    'levntar': 'levantar', 'levanat': 'levanta', 'prende': 'prende', 'prendelo': 'prende', 'enciende': 'enciende',
    'enciendelo': 'enciende', 'encinde': 'enciende', 'encender': 'encender', 'apagalo': 'apaga', 'apga': 'apaga',
    'apgar': 'apagar', 'recarga': 'recarga', 'recargar': 'recargar', 'habilita': 'habilita', 'habilitar': 'habilitar',
    'deshabilita': 'deshabilita', 'deshabilitar': 'deshabilitar', 'inhabilita': 'deshabilita',
    # buscar
    'buscra': 'busca', 'buska': 'busca', 'bsuca': 'busca', 'buscaa': 'busca', 'bucsa': 'busca', 'buscame': 'busca',
    'buscalo': 'busca', 'encuentrame': 'encuentra', 'encuentra': 'encuentra', 'localiza': 'encuentra',
    'googlea': 'googlea', 'gogglea': 'googlea', 'investiga': 'investiga', 'investigame': 'investiga',
    # instalar / actualizar
    'intala': 'instala', 'isntala': 'instala', 'instlaa': 'instala', 'instalaa': 'instala', 'instlar': 'instalar',
    'isntalar': 'instalar', 'instalame': 'instala', 'actualzia': 'actualiza', 'actualiza': 'actualiza',
    'actulaiza': 'actualiza', 'actualisa': 'actualiza', 'actualizar': 'actualizar', 'acutalizar': 'actualizar',
    'desinstala': 'desinstala', 'desinstlar': 'desinstalar',
    # leer / archivos
    'lee': 'lee', 'leelo': 'lee', 'lme': 'lee', 'muevelo': 'mueve', 'mueve': 'mueve', 'mover': 'mover', 'mvoer': 'mover',
    'renombrar': 'renombrar', 'renombra': 'renombra', 'copia': 'copia', 'copiar': 'copiar', 'cpia': 'copia',
    'archivo': 'archivo', 'archvo': 'archivo', 'achivo': 'archivo', 'arhivo': 'archivo', 'arvhivo': 'archivo',
    'archvios': 'archivos', 'achivos': 'archivos', 'carpta': 'carpeta', 'capeta': 'carpeta', 'carpetta': 'carpeta',
    'carepta': 'carpeta', 'directrio': 'directorio', 'direcotrio': 'directorio', 'direcorio': 'directorio',
    # sistema
    'sistma': 'sistema', 'sitema': 'sistema', 'sisetma': 'sistema', 'sistem': 'sistema', 'sitsema': 'sistema',
    'memria': 'memoria', 'memorai': 'memoria', 'memroia': 'memoria', 'procesdor': 'procesador', 'procesadro': 'procesador',
    'proceso': 'proceso', 'procesoss': 'procesos', 'proceos': 'procesos', 'porcesos': 'procesos', 'prcesos': 'procesos',
    'servidr': 'servidor', 'sevidor': 'servidor', 'servidro': 'servidor', 'sevrvidor': 'servidor', 'servdor': 'servidor',
    'servcio': 'servicio', 'sevicio': 'servicio', 'servico': 'servicio', 'servcios': 'servicios', 'sevicios': 'servicios',
    'tempertura': 'temperatura', 'temperatua': 'temperatura', 'temeratura': 'temperatura', 'bateia': 'bateria',
    'baterai': 'bateria', 'bateria': 'bateria', 'volumne': 'volumen', 'volmen': 'volumen', 'volumn': 'volumen',
    'brilo': 'brillo', 'brillio': 'brillo', 'briyo': 'brillo', 'pantala': 'pantalla', 'patalla': 'pantalla',
    'pantlla': 'pantalla', 'usuaro': 'usuario', 'usurio': 'usuario', 'usuarios': 'usuarios', 'usarios': 'usuarios',
    'conexon': 'conexion', 'cnexion': 'conexion', 'cenexion': 'conexion', 'wfi': 'wifi', 'wif': 'wifi', 'wi-fi': 'wifi',
    'wi fi': 'wifi', 'blutooth': 'bluetooth', 'bluetoth': 'bluetooth', 'bluetoot': 'bluetooth', 'blutuz': 'bluetooth',
    'internte': 'internet', 'inernet': 'internet', 'intenet': 'internet', 'interent': 'internet', 'intrenet': 'internet',
    'puertro': 'puerto', 'puertoss': 'puertos', 'puetos': 'puertos', 'peurtos': 'puertos', 'purtos': 'puertos',
    'ipp': 'ip', 'dirección': 'direccion', 'direcion': 'direccion', 'direccon': 'direccion',
    'logss': 'logs', 'losg': 'logs', 'regsitros': 'registros', 'registors': 'registros',
    'espcio': 'espacio', 'espaico': 'espacio', 'discoo': 'disco', 'dsico': 'disco', 'dicso': 'disco',
    'ramm': 'ram', 'rma': 'ram', 'cpuu': 'cpu', 'gpuu': 'gpu', 'ocupa': 'ocupa', 'consme': 'consume',
    'consumne': 'consumen', 'consumem': 'consumen',
    'hora': 'hora', 'hroa': 'hora', 'fehca': 'fecha', 'fehca': 'fecha', 'zona orari': 'zona horaria',
    'pf': 'por favor', 'porfa': 'por favor', 'porfis': 'por favor', 'xfa': 'por favor', 'pls': 'por favor',
    'plis': 'por favor', 'porfavor': 'por favor', 'pofavor': 'por favor', 'xfavor': 'por favor',
    'navegdor': 'navegador', 'naegador': 'navegador', 'nabegador': 'navegador', 'terminl': 'terminal', 'termianl': 'terminal',
    'teminal': 'terminal', 'termnal': 'terminal', 'conola': 'consola',
    'nmpa': 'nmap', 'namp': 'nmap', 'pign': 'ping', 'pinng': 'ping', 'tracerotue': 'traceroute', 'taceroute': 'traceroute',
    'firewal': 'firewall', 'firwall': 'firewall', 'fierwall': 'firewall', 'sudoo': 'sudo',
    'cierar': 'cerrar', 'cerar': 'cerrar', 'cierra': 'cierra', 'bloquea': 'bloquea', 'bloquear': 'bloquear',
    'blokea': 'bloquea', 'bloqea': 'bloquea', 'suspnde': 'suspende', 'suspendr': 'suspender', 'hibrenar': 'hibernar',
    'captrua': 'captura', 'catpura': 'captura', 'capura': 'captura', 'screnshot': 'screenshot', 'screenshoot': 'screenshot',
    'portapaples': 'portapapeles', 'portapapeles': 'portapapeles', 'protapapeles': 'portapapeles',
    'matar': 'matar', 'mata': 'mata', 'matalo': 'mata', 'finaliza': 'termina', 'finalizar': 'terminar',
    'kilal': 'killall', 'kil': 'kill', 'pkil': 'pkill',
}

# ======================================================================
# Números escritos con letras (para «volumen al cincuenta», «puerto ocho mil»)
# ======================================================================
NUMBER_WORDS = {
    'cero': 0, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8,
    'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15, 'dieciseis': 16,
    'diecisiete': 17, 'dieciocho': 18, 'diecinueve': 19, 'veinte': 20, 'veintiuno': 21, 'veintidos': 22,
    'veintitres': 23, 'veinticuatro': 24, 'veinticinco': 25, 'veintiseis': 26, 'veintisiete': 27, 'veintiocho': 28,
    'veintinueve': 29, 'treinta': 30, 'cuarenta': 40, 'cincuenta': 50, 'sesenta': 60, 'setenta': 70, 'ochenta': 80,
    'noventa': 90, 'cien': 100, 'ciento': 100, 'doscientos': 200, 'trescientos': 300, 'quinientos': 500,
    'mil': 1000,
}