from dotenv import dotenv_values
import os
import subprocess


if __name__ == "__main__":
    env = dotenv_values()
    line = env["LINE_DNS_TOKEN"]
    web = env["WEB_DNS_TOKEN"]

    if os.name == "nt":
        os.system(f"start cmd /k tunnel run --token {line}")
        os.system(f"start cmd /k tunnel run --token {web}")
    else:
        cmd_line = f"tunnel run --token {line} && read"
        cmd_web = f"tunnel run --token {line} && read"

        for c in [cmd_line, cmd_web]:
            apple_script = f"""
            tell application "Terminal"
                do script "{c}"
                activate
            end tell
            """

            subprocess.run(["osascript", "-e", apple_script])
