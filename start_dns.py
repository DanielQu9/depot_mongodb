from dotenv import dotenv_values
import os
import subprocess


if __name__ == "__main__":
    env = dotenv_values()
    line = f'cloudflared tunnel run --token {env["LINE_DNS_TOKEN"]}'
    web = f'cloudflared tunnel run --token {env["WEB_DNS_TOKEN"]}'

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
