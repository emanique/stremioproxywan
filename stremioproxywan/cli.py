#!/usr/bin/env python3
"""Local CLI; safe changes are performed with backup and nginx -t before reload."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from .config import CONFIG_FILE, DEFAULTS, validate, nginx_config, require_deployment_values

ROOT = Path('/etc/stremioproxywan')
TARGET = Path('/etc/nginx/sites-available/stremioproxywan.conf')
LINK = Path('/etc/nginx/sites-enabled/stremioproxywan.conf')
KEY = ROOT / 'session.key'
PASSWD = ROOT / 'users.htpasswd'
UNIT = Path('/etc/systemd/system/stremioproxywan-session.service')

def run(args, **kw):
    return subprocess.run(args, check=True, **kw)

def root_only():
    if os.geteuid() != 0:
        raise SystemExit('Run as root (sudo).')

def permissions():
    ROOT.mkdir(mode=0o750, parents=True, exist_ok=True)
    ROOT.chmod(0o750)
    shutil.chown(ROOT, user='root', group='www-data')

def load():
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    return validate(json.loads(CONFIG_FILE.read_text()))

def save(data):
    data = validate(data)
    permissions()
    tmp = ROOT / 'config.json.tmp'
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    tmp.chmod(0o600)
    tmp.replace(CONFIG_FILE)

def cert_san(host):
    try:
        import ipaddress
        ipaddress.ip_address(host)
        return 'IP:' + host
    except ValueError:
        return 'DNS:' + host

def generate_selfsigned(data):
    """Generate only when absent; no surprise key rotation on upgrade."""
    cert = Path(data['wan_cert'])
    key = Path(data['wan_key'])
    if cert.exists() and key.exists():
        return
    if cert.exists() != key.exists():
        raise RuntimeError('Only one of certificate/key exists. Refusing to overwrite.')
    cert.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    key.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    run(['openssl','req','-x509','-newkey','rsa:3072','-sha256','-nodes',
         '-keyout',str(key),'-out',str(cert),'-days','365',
         '-subj',f'/CN={data["wan_host"]}',
         '-addext',f'subjectAltName={cert_san(data["wan_host"])}'])
    key.chmod(0o600)
    cert.chmod(0o644)

def ensure_secret():
    if not KEY.exists():
        KEY.write_text(secrets.token_hex(32) + '\n')
    KEY.chmod(0o640)
    shutil.chown(KEY, user='root', group='www-data')

def ensure_users():
    if not PASSWD.exists() or PASSWD.stat().st_size == 0:
        raise RuntimeError('No WAN user found. Run: sudo stremioproxywan user add USERNAME')
    PASSWD.chmod(0o640)
    shutil.chown(PASSWD, user='root', group='www-data')

def preflight(data):
    if not CONFIG_FILE.is_file():
        raise RuntimeError('Configure WAN/LAN details before deploying')
    require_deployment_values(data)
    for cmd in ('nginx','systemctl','openssl','htpasswd'):
        if not shutil.which(cmd):
            raise RuntimeError(f'Missing required executable: {cmd}')
    if data['backend_scheme'] == 'https' and not Path(data['backend_ca']).is_file():
        raise RuntimeError('Backend CA bundle does not exist')
    if data['wan_tls_mode'] == 'trusted':
        if not (Path(data['wan_cert']).is_file() and Path(data['wan_key']).is_file()):
            raise RuntimeError('Trusted certificate and key must be installed before apply')
    if (TARGET.exists() or LINK.exists()) and not LINK.is_symlink() and LINK.exists():
        raise RuntimeError('Existing non-symlink sites-enabled file; refuse to overwrite')
    if LINK.is_symlink() and LINK.resolve() != TARGET:
        raise RuntimeError('sites-enabled symlink points to a different file')

def backup():
    if not TARGET.exists():
        return None
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = ROOT / f'backup-stremioproxywan-{ts}.conf'
    shutil.copy2(TARGET,destination)
    destination.chmod(0o600)
    return destination

def apply():
    root_only()
    data=load()
    preflight(data)
    permissions()
    ensure_users()
    ensure_secret()
    if data['wan_tls_mode']=='selfsigned':
        generate_selfsigned(data)
    generated=nginx_config(data)
    old=TARGET.read_bytes() if TARGET.exists() else None
    old_link=LINK.is_symlink()
    previous=backup()
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    TARGET.write_text(generated)
    TARGET.chmod(0o644)
    if not old_link:
        LINK.symlink_to(TARGET)
    try:
        run(['nginx','-t'],capture_output=True,text=True)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr,file=sys.stderr)
        if old is not None:
            TARGET.write_bytes(old)
        else:
            TARGET.unlink(missing_ok=True)
            if not old_link:
                LINK.unlink(missing_ok=True)
        raise RuntimeError('nginx -t failed; configuration restored; no reload') from exc
    UNIT.write_text('''[Unit]\nDescription=StremioProxyWAN session issuer\nAfter=network.target\n[Service]\nType=simple\nUser=www-data\nGroup=www-data\nEnvironment=STREMIOPROXYWAN_KEY_FILE=/etc/stremioproxywan/session.key\nExecStart=/usr/bin/python3 /usr/lib/stremioproxywan/stremioproxywan/session.py\nRestart=on-failure\nRestartSec=3\nNoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=strict\nProtectHome=true\nReadOnlyPaths=/etc/stremioproxywan/session.key\nRestrictAddressFamilies=AF_INET AF_UNIX\n[Install]\nWantedBy=multi-user.target\n''')
    try:
        run(['systemctl','daemon-reload'])
        run(['systemctl','enable','--now','stremioproxywan-session.service'])
        run(['systemctl','reload','nginx'])
    except subprocess.CalledProcessError:
        if old is not None:
            TARGET.write_bytes(old)
        else:
            TARGET.unlink(missing_ok=True)
            if not old_link:
                LINK.unlink(missing_ok=True)
        run(['nginx','-t'])
        run(['systemctl','reload','nginx'])
        raise
    print('Applied; backup:',previous or 'first installation')

def update_user(action, name):
    root_only()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',name):
        raise RuntimeError('Username: 1-64 ASCII letters, numbers, _, -, .')
    permissions()
    if action == 'remove':
        if not PASSWD.exists():
            raise RuntimeError('User database absent')
        all_users = [line.split(':',1)[0] for line in PASSWD.read_text().splitlines() if ':' in line]
        if name not in all_users or len(all_users) < 2:
            raise RuntimeError('Unknown user or cannot delete the last WAN user')
        run(['htpasswd','-D',str(PASSWD),name])
    else:
        password=getpass.getpass('New WAN password: ')
        confirm=getpass.getpass('Repeat WAN password: ')
        if password!=confirm or len(password)<12:
            raise RuntimeError('Passwords differ or contain fewer than 12 characters')
        cmd=['htpasswd','-B','-i']
        if not PASSWD.exists():
            cmd.append('-c')
        if action == 'password' and (not PASSWD.exists() or not any(line.startswith(name+':') for line in PASSWD.read_text().splitlines())):
            raise RuntimeError('User does not exist; use user add')
        cmd += [str(PASSWD),name]
        run(cmd,input=password+'\n',text=True,stdout=subprocess.DEVNULL)
    PASSWD.chmod(0o640)
    shutil.chown(PASSWD,user='root',group='www-data')
    print(f'WAN user {action} completed. Existing sessions remain valid until expiry.')

def main(argv=None):
    parser=argparse.ArgumentParser(prog='stremioproxywan')
    sub=parser.add_subparsers(dest='cmd',required=True)
    cfg=sub.add_parser('configure',help='set host, ports, TLS and HTTP policy')
    cfg.add_argument('--set',action='append',required=True,metavar='KEY=VALUE')
    sub.add_parser('show')
    sub.add_parser('check')
    sub.add_parser('apply')
    user=sub.add_parser('user')
    user.add_argument('action',choices=('add','password','remove','list'))
    user.add_argument('username',nargs='?')
    args=parser.parse_args(argv)
    try:
        if args.cmd=='configure':
            root_only()
            data=load()
            for item in args.set:
                if '=' not in item:
                    raise ValueError('Expected KEY=VALUE')
                key,val=item.split('=',1)
                if key not in DEFAULTS:
                    raise ValueError(f'Unsupported key: {key}')
                data[key]=val
            save(data)
            print('Saved configuration; run check then apply')
        elif args.cmd=='show':
            print(json.dumps(load(),indent=2,sort_keys=True))
        elif args.cmd=='check':
            d=load()
            preflight(d)
            print('Configuration parameters validated; nginx validation occurs during apply')
        elif args.cmd=='apply':
            apply()
        elif args.cmd=='user':
            root_only()
            if args.action=='list':
                if PASSWD.exists():
                    for entry in PASSWD.read_text().splitlines():
                        if ':' in entry:
                            print(entry.split(':',1)[0])
            else:
                if not args.username:
                    parser.error('username required')
                update_user(args.action,args.username)
    except (ValueError,RuntimeError,OSError) as exc:
        raise SystemExit(f'ERROR: {exc}') from exc

if __name__=='__main__':
    main()
