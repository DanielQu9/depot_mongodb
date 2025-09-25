from dotenv import dotenv_values
import os
import subprocess


if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))
    if not os.path.exists("./.env"):
        token_str = 'LINE_CHANNEL_SECRET=""\nLINE_CHANNEL_ACCESS_TOKEN=""\nLINE_DNS_TOKEN=""\nWEB_DNS_TOKEN=""'
        with open(file="./.env", mode="w", encoding="utf-8") as file:
            file.write(token_str)
            print(">> 請填寫api")
        os._exit(0)

    env = dotenv_values()
    try:
        line = f'cloudflared tunnel run --token {env["LINE_DNS_TOKEN"]}'
        web = f'cloudflared tunnel run --token {env["WEB_DNS_TOKEN"]}'
    except KeyError:
        print(">> 請填寫api")
        os._exit(0)

    if os.name == "nt":
        os.system(f"start cmd /k {line}")
        os.system(f"start cmd /k {web}")
    else:
        for c in [line, web]:
            apple_script = f"""
            tell application "Terminal"
                do script "{c}"
                activate
            end tell
            """

            subprocess.run(["osascript", "-e", apple_script])
