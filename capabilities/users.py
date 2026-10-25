"""Non-sensitive local user and group inspection."""
import pwd, grp, os
def current():return {'uid':os.getuid(),'username':pwd.getpwuid(os.getuid()).pw_name,'groups':os.getgroups()}
def users():return [{'name':p.pw_name,'uid':p.pw_uid,'gid':p.pw_gid,'home':p.pw_dir} for p in pwd.getpwall() if p.pw_uid>=1000 or p.pw_uid==0]
def groups():return [{'name':g.gr_name,'gid':g.gr_gid,'members':g.gr_mem} for g in grp.getgrall()]
def exists(name):
    try:pwd.getpwnam(name);return True
    except KeyError:return False
