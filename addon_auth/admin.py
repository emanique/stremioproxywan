"""Root-only control to explicitly approve/revoke a Stremio account id."""
import argparse
import os
from .service import authorize_account, revoke_account, load
def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("allow","revoke","list"))
    p.add_argument("account", nargs="?")
    args=p.parse_args()
    if args.action == "list":
        for account in sorted(load()["accounts"]):
            print(account)
        return
    if not args.account:
        p.error("account id required")
    if args.action == "allow":
        authorize_account(args.account)
    else:
        revoke_account(args.account)
    print("Account policy updated")
if __name__=="__main__":
    main()
