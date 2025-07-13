from dotenv import dotenv_values
import os
import subprocess


if __name__ == "__main__":
    env = dotenv_values()
    line = env["LINE_DNS_TOKEN"]
    web = env["WEB_DNS_TOKEN"]

    if os.name == "nt":
        os.system(f"start cmd /k cloudflared tunnel run --token {line}")
        os.system(f"start cmd /k cloudflared tunnel run --token {web}")
    else:
        cmd_line = f"cloudflared tunnel run --token {line}"
        cmd_web = f"cloudflared tunnel run --token {web}"

        for c in [cmd_line, cmd_web]:
            apple_script = f"""
            tell application "Terminal"
                do script "{c}"
                activate
            end tell
            """

            subprocess.run(["osascript", "-e", apple_script])
