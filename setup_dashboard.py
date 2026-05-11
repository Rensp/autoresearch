#!/usr/bin/env python3
"""
Eenmalige setup en start van het DAX Turbo dashboard.

Gebruik:
    uv run setup_dashboard.py
"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env"

GROEN = "\033[92m"
GEEL = "\033[93m"
ROOD = "\033[91m"
BLAUW = "\033[94m"
RESET = "\033[0m"
VET = "\033[1m"


def print_stap(nr, tekst):
    print(f"\n{BLAUW}{VET}[{nr}]{RESET} {tekst}")


def print_ok(tekst):
    print(f"  {GROEN}✓{RESET} {tekst}")


def print_info(tekst):
    print(f"  {GEEL}→{RESET} {tekst}")


def print_fout(tekst):
    print(f"  {ROOD}✗{RESET} {tekst}")


def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print_fout(f"Commando mislukt: {cmd}")
        print(result.stderr[:500])
        sys.exit(1)
    return result


def main():
    print(f"\n{VET}{'='*50}")
    print("  DAX Turbo Pro — Setup")
    print(f"{'='*50}{RESET}\n")

    # ── Stap 1: git pull ──────────────────────────────────────────────────────
    print_stap(1, "Laatste versie ophalen van GitHub...")
    os.chdir(ROOT)
    result = run("git pull", check=False)
    if result.returncode == 0:
        print_ok("Code up-to-date")
    else:
        print_info("git pull overgeslagen (mogelijk niet verbonden)")

    # ── Stap 2: dependencies installeren ─────────────────────────────────────
    print_stap(2, "Python packages installeren...")
    run("uv sync --extra dashboard")
    print_ok("Alle packages geïnstalleerd")

    # ── Stap 3: .env bestand aanmaken ─────────────────────────────────────────
    print_stap(3, "DEGIRO inloggegevens instellen...")

    if ENV_FILE.exists():
        # Check if credentials are already filled in
        env_content = ENV_FILE.read_text()
        has_user = "DEGIRO_USERNAME=" in env_content and "jouw@email" not in env_content
        has_pass = "DEGIRO_PASSWORD=" in env_content and "jouwwachtwoord" not in env_content
        if has_user and has_pass:
            print_ok(".env bestand al aanwezig met inloggegevens — overgeslagen")
        else:
            print_info(".env bestand gevonden maar inloggegevens nog niet ingevuld")
            _vraag_credentials()
    else:
        print_info("Geen .env bestand gevonden — aanmaken...")
        _vraag_credentials()

    # ── Stap 4: starten ───────────────────────────────────────────────────────
    print_stap(4, "Dashboard starten...")
    print_ok("Open je browser op: http://localhost:8501")
    print_info("Druk Ctrl+C om te stoppen\n")

    os.execvp("uv", [
        "uv", "run", "--extra", "dashboard",
        "streamlit", "run", "dashboard/app.py",
        "--server.port", "8501",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ])


def _vraag_credentials():
    print()
    print(f"  {VET}Voer je DEGIRO inloggegevens in.{RESET}")
    print(f"  {GEEL}Deze worden opgeslagen in .env op jouw computer — nergens anders.{RESET}\n")

    username = input("  DEGIRO gebruikersnaam (e-mailadres): ").strip()
    if not username:
        print_fout("Gebruikersnaam mag niet leeg zijn")
        sys.exit(1)

    password = getpass.getpass("  DEGIRO wachtwoord (wordt niet getoond): ")
    if not password:
        print_fout("Wachtwoord mag niet leeg zijn")
        sys.exit(1)

    print()
    heeft_2fa = input("  Heb je 2FA (twee-factor authenticatie) ingeschakeld? [j/N]: ").strip().lower()
    totp_secret = ""
    if heeft_2fa in ("j", "ja", "y", "yes"):
        print(f"  {GEEL}Ga naar DEGIRO → Instellingen → Beveiliging → 2FA en kopieer de SECRET KEY{RESET}")
        print(f"  {GEEL}(Dit is NIET de 6-cijferige code, maar de lange sleutel eronder){RESET}")
        totp_secret = getpass.getpass("  TOTP geheime sleutel: ").strip()

    # Schrijf .env
    lines = [
        "# DEGIRO inloggegevens — automatisch aangemaakt door setup_dashboard.py",
        f"DEGIRO_USERNAME={username}",
        f"DEGIRO_PASSWORD={password}",
    ]
    if totp_secret:
        lines.append(f"DEGIRO_TOTP_SECRET={totp_secret}")

    ENV_FILE.write_text("\n".join(lines) + "\n")
    os.chmod(ENV_FILE, 0o600)  # Alleen leesbaar voor eigenaar

    print_ok(f".env aangemaakt ({ENV_FILE})")
    print_ok("Bestandsrechten ingesteld op 600 (alleen jij kan het lezen)")


if __name__ == "__main__":
    main()
