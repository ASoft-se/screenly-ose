import os, shutil, subprocess

# Ensure config file is in place
conf_file = os.path.join(os.getenv('HOME'), '.screenly', 'screenly.conf')
if not os.path.isfile(conf_file):
    print "Copying in config file..."
    example_conf = os.path.join(os.getenv('HOME'), 'screenly', 'misc', 'screenly.conf')    
    shutil.copy(example_conf, conf_file)

# Updating symlink for supervisor
supervisor_symlink = '/etc/supervisor/conf.d/screenly.conf'
old_target = '/home/pi/screenly/misc/screenly.conf'
new_target = '/home/pi/screenly/misc/supervisor_screenly.conf'

if os.path.isfile(supervisor_symlink) and os.readlink(supervisor_symlink) == old_target:
    print 'Updating Supervisor symlink'
    try:
        subprocess.call(['/usr/bin/sudo', 'rm', supervisor_symlink])
    except:
        print 'Failed to remove symlink.'
    try:
        subprocess.call(['/usr/bin/sudo', 'ln', '-s', new_target, supervisor_symlink])
    except:
        print 'Failed to create symlink'

print "Migration done."
