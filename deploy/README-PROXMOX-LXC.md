# Przenoszenie na Proxmox LXC

Aplikacja jest zrobiona tak, żeby łatwo przenieść ją z sieci lokalnej do
kontenera LXC na Proxmox. Dwie opcje:

## Opcja A: kontener LXC + Docker (najmniej ręcznej pracy)

1. Utwórz w Proxmox kontener LXC (Debian/Ubuntu 12, **unprivileged** nie jest
   wymagany ale polecany), min. 1 vCPU / 512 MB RAM / 2 GB dysku.
2. Zainstaluj Docker w kontenerze:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
   (W LXC może być wymagane `nesting=1` i `keyctl=1` we Options kontenera,
   ustawiane z hosta Proxmox: `pct set <ID> -features nesting=1,keyctl=1`)
3. Skopiuj repo do kontenera (`git clone` albo `scp`), np. do `/opt/bachata-events-pl`.
4. `cp .env.example .env` i ustaw `ADMIN_TOKEN`.
5. `docker compose up -d --build`
6. Aplikacja działa na porcie 8000 kontenera — wystaw go w sieci LAN przez
   adres IP kontenera (Proxmox przydziela go automatycznie przy moście vmbr).

## Opcja B: kontener LXC bez Dockera (systemd + venv)

1. W kontenerze LXC: `apt install python3 python3-venv git -y`
2. `git clone <repo> /opt/bachata-events-pl && cd /opt/bachata-events-pl`
3. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
4. `cp .env.example .env` i ustaw wartości.
5. Skopiuj jednostki systemd z `deploy/`:
   ```bash
   cp deploy/bachata-events.service /etc/systemd/system/
   cp deploy/bachata-scraper.service /etc/systemd/system/
   cp deploy/bachata-scraper.timer /etc/systemd/system/
   useradd -r -s /usr/sbin/nologin bachata || true
   chown -R bachata:bachata /opt/bachata-events-pl
   systemctl daemon-reload
   systemctl enable --now bachata-events.service
   systemctl enable --now bachata-scraper.timer
   ```
6. Sprawdź: `systemctl status bachata-events.service`, `journalctl -u bachata-events.service -f`.

## Dostęp z sieci lokalnej

Niezależnie od opcji, aplikacja nasłuchuje na `0.0.0.0:8000`. Żeby była
widoczna z całej sieci lokalnej:

- Na obecnej maszynie (bez LXC): uruchom `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  i wejdź z innego urządzenia pod `http://<IP-tej-maszyny>:8000`.
- W Proxmox LXC: kontener z mostem `vmbr0` dostaje własny adres w tej samej
  sieci LAN — używaj `http://<IP-kontenera>:8000`.
- Opcjonalnie dodaj reverse proxy (np. Caddy/nginx w LXC) dla ładnego URL
  typu `http://bachata.local`.

## Migracja danych

Baza SQLite to jeden plik: `data/bachata_events.db`. Przy migracji wystarczy
skopiować cały katalog `data/` do nowego środowiska — nic więcej nie trzeba
przenosić.
